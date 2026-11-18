from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from ..models import (
    DataSource,
    DataImport, Practice
)
from .serializers import (
    DataImportSerializer,
    DataSourceSerializer, PracticeSerializer
)
from django.db import connection


from django.db import connection
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


class PracticeViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Practice.objects.order_by("id")
    serializer_class = PracticeSerializer

    @extend_schema(
        summary="Lister les pratiques",
        description="""
        Permet de filtrer les pratiques selon plusieurs critères :

        - has_parent : filtrer les pratiques ayant ou non un parent.
        - code : rechercher une pratique par son code.
        - parent_id : récupérer les enfants d'un parent.
        - parent_code : récupérer les enfants d'un parent identifié par son code.
        - recursive : inclure tous les descendants du parent.

        Le paramètre recursive fonctionne avec parent_id ou parent_code.
        """,
        parameters=[
            OpenApiParameter(
                name="has_parent",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="true : pratiques avec parent ; false : pratiques sans parent.",
            ),
            OpenApiParameter(
                name="code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Recherche par code de la pratique.",
            ),
            OpenApiParameter(
                name="parent_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="ID du parent dont on veut récupérer les enfants.",
            ),
            OpenApiParameter(
                name="parent_code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Code du parent dont on veut récupérer les enfants.",
            ),
            OpenApiParameter(
                name="recursive",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="true : récupérer tous les descendants, y compris les enfants indirects.",
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        has_parent = params.get("has_parent")

        if has_parent == "true":
            queryset = queryset.filter(parent__isnull=False)
        elif has_parent == "false":
            queryset = queryset.filter(parent__isnull=True)

        code = params.get("code")

        if code:
            queryset = queryset.filter(code__icontains=code)

        parent_id = params.get("parent_id")
        if parent_id is not None and not parent_id.isdigit():
            raise ValidationError({"parent_id": "Un entier est attendu."})
        parent_code = params.get("parent_code")

        recursive = params.get("recursive", "false").lower() == "true"

        # Recherche du parent par son code
        if parent_code and not parent_id:
            parent = Practice.objects.filter(code__iexact=parent_code).first()

            if not parent:
                return queryset.none()

            parent_id = parent.id

        if parent_id:
            if recursive:
                table = connection.ops.quote_name(
                    Practice._meta.db_table
                )

                sql = f"""
                    WITH RECURSIVE practice_tree AS (
                        SELECT id
                        FROM {table}
                        WHERE parent_id = %s

                        UNION

                        SELECT p.id
                        FROM {table} p
                        INNER JOIN practice_tree pt
                            ON p.parent_id = pt.id
                    )
                    SELECT id FROM practice_tree
                """

                with connection.cursor() as cursor:
                    cursor.execute(sql, [parent_id])
                    ids = [row[0] for row in cursor.fetchall()]

                queryset = queryset.filter(id__in=ids)

            else:
                queryset = queryset.filter(parent_id=parent_id)

        return queryset

class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = DataSource.objects.order_by("id")
    serializer_class = DataSourceSerializer

class DataImportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataImport.objects.order_by("date_import")
    serializer_class = DataImportSerializer
