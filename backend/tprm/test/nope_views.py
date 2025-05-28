from django.test import TestCase
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from tprm.models import Entity, EntityAssessment, Representative
from core.models import Perimeter, ComplianceAssessment
from tprm.views import EntityViewSet, EntityAssessmentViewSet
from iam.models import Folder

from django.contrib.auth import get_user_model

User = get_user_model()


class TestEntityViewSet(TestCase):
    def setUp(self):
        """Initial configuration for entity view tests."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password"
        )

        self.folder = Folder.objects.create(name="Test Folder")
        self.entity = Entity.objects.create(name="Test Entity", folder=self.folder)

    def test_list_entities(self):
        """Entity list test."""
        view = EntityViewSet.as_view({"get": "list"})
        request = self.factory.get("/api/entities/")
        force_authenticate(request, user=self.user)

        with patch(
            "tprm.views.RoleAssignment.get_accessible_object_ids"
        ) as mock_get_accessible:
            mock_get_accessible.return_value = ([self.entity.id], None, None)
            response = view(request)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("results", response.data)

    def test_retrieve_entity(self):
        """Test de la récupération d'une entité."""
        view = EntityViewSet.as_view({"get": "retrieve"})
        request = self.factory.get(f"/api/entities/{self.entity.id}/")
        force_authenticate(request, user=self.user)

        with patch(
            "tprm.views.RoleAssignment.get_accessible_object_ids"
        ) as mock_get_accessible:
            # Pour la visualisation, on n'a besoin que des droits de lecture
            mock_get_accessible.return_value = ([self.entity.id], [], [])
            response = view(request, pk=self.entity.id)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["name"], "Test Entity")

    def test_create_entity(self):
        """Test de la création d'une entité."""
        view = EntityViewSet.as_view({"post": "create"})
        data = {
            "name": "New Entity",
            "description": "New description",
            "folder": self.folder.id,
            "is_published": True,
        }
        request = self.factory.post("/api/entities/", data)
        force_authenticate(request, user=self.user)

        with (
            patch(
                "tprm.views.RoleAssignment.get_accessible_object_ids"
            ) as mock_get_accessible,
            patch("iam.models.RoleAssignment.has_permission") as mock_has_permission,
        ):
            mock_get_accessible.return_value = ([self.entity.id], None, None)
            mock_has_permission.return_value = True
            response = view(request, pk=self.entity.id)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["name"], "New Entity")

    def test_update_entity(self):
        """Test de la mise à jour d'une entité."""
        view = EntityViewSet.as_view({"put": "update"})
        data = {
            "name": "Updated Entity",
            "folder": self.folder.id,
            "is_published": True,
        }
        request = self.factory.put(f"/api/entities/{self.entity.id}/", data)
        force_authenticate(request, user=self.user)

        with patch(
            "tprm.views.RoleAssignment.get_accessible_object_ids"
        ) as mock_get_accessible:
            mock_get_accessible.return_value = ([self.entity.id], None, None)
            response = view(request, pk=self.entity.id)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["name"], "Updated Entity")

    def test_delete_entity(self):
        """Test de la suppression d'une entité."""
        view = EntityViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/api/entities/{self.entity.id}/")
        force_authenticate(request, user=self.user)

        with patch(
            "tprm.views.RoleAssignment.get_accessible_object_ids"
        ) as mock_get_accessible:
            mock_get_accessible.return_value = ([self.entity.id], None, None)
            response = view(request, pk=self.entity.id)

            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            with self.assertRaises(Entity.DoesNotExist):
                Entity.objects.get(id=self.entity.id)


class TestEntityAssessmentViewSet(TestCase):
    def setUp(self):
        """Configuration initiale pour les tests de vue d'évaluation d'entité."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password"
        )

        self.folder = Folder.objects.create(name="Test Folder")
        self.entity = Entity.objects.create(name="Test Entity", folder=self.folder)

        # Créer une vraie instance de Perimeter
        self.perimeter = Perimeter.objects.create(
            name="Test Perimeter", folder=self.folder
        )

        self.assessment = EntityAssessment.objects.create(
            name="Test Assessment",
            entity=self.entity,
            folder=self.folder,
            perimeter=self.perimeter,
        )

    def test_status_action(self):
        """Test de l'action status."""
        view = EntityAssessmentViewSet.as_view({"get": "status"})
        request = self.factory.get("/api/entity-assessments/status/")
        force_authenticate(request, user=self.user)

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("planned", response.data)

    def test_conclusion_action(self):
        """Test de l'action conclusion."""
        view = EntityAssessmentViewSet.as_view({"get": "conclusion"})
        request = self.factory.get("/api/entity-assessments/conclusion/")
        force_authenticate(request, user=self.user)

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("blocker", response.data)

    @patch("tprm.views.RoleAssignment.get_accessible_object_ids")
    @patch("tprm.models.EntityAssessment.objects.filter")
    def test_metrics_action(self, mock_filter, mock_get_accessible):
        """Test de l'action metrics."""
        view = EntityAssessmentViewSet.as_view({"get": "metrics"})
        request = self.factory.get("/api/entity-assessments/metrics/")
        force_authenticate(request, user=self.user)

        # Mock pour simuler que l'utilisateur a accès à l'assessment
        mock_get_accessible.return_value = ([self.assessment.id], None, None)

        # Créer un mock pour framework
        mock_framework = MagicMock()
        mock_framework.name = "Test Framework"

        # Configurer les mocks pour l'objet EntityAssessment
        mock_ea = MagicMock(spec=EntityAssessment)
        mock_ea.id = self.assessment.id
        mock_ea.entity = self.entity
        mock_ea.solutions = MagicMock()
        mock_ea.solutions.all.return_value = []

        # Configurer compliance_assessment
        mock_compliance = MagicMock()
        mock_compliance.framework = mock_framework
        mock_compliance.id = "ca-id"
        mock_compliance.has_questions = True
        mock_compliance.answers_progress = 75
        mock_compliance.progress = 50

        mock_ea.compliance_assessment = mock_compliance
        mock_ea.due_date = None
        mock_ea.updated_at = None
        mock_ea.conclusion = None
        mock_ea.reviewers = MagicMock()
        mock_ea.reviewers.all.return_value = []
        mock_ea.observation = None

        # Configurer le mock pour filter
        mock_filter.return_value = [mock_ea]

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["entity_assessment_id"], self.assessment.id)
        self.assertEqual(response.data[0]["provider"], self.entity.name)
        self.assertEqual(response.data[0]["baseline"], "Test Framework")
        self.assertEqual(response.data[0]["completion"], 75)
        self.assertEqual(response.data[0]["review_progress"], 50)

    def test_destroy_with_compliance_assessment(self):
        """Test de la suppression d'une évaluation avec compliance_assessment."""
        view = EntityAssessmentViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/api/entity-assessments/{self.assessment.id}/")
        force_authenticate(request, user=self.user)

        # Créer un mock avec l'attribut _state
        mock_compliance = MagicMock(spec=ComplianceAssessment)
        mock_state = MagicMock()
        mock_state.db = "default"  # Simuler que l'objet existe en base
        mock_compliance._state = mock_state

        # Assigner le mock
        self.assessment.compliance_assessment = mock_compliance

        mock_folder = MagicMock()
        mock_folder.content_type = Folder.ContentType.ENCLAVE
        mock_compliance.folder = mock_folder

        with patch(
            "tprm.views.RoleAssignment.get_accessible_object_ids"
        ) as mock_get_accessible:
            mock_get_accessible.return_value = ([self.assessment.id], None, None)
            response = view(request, pk=self.assessment.id)

            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            mock_compliance.delete.assert_called_once()
            mock_folder.delete.assert_called_once()


class TestRepresentativeViewSet(TestCase):
    def setUp(self):
        """Configuration initiale pour les tests de vue de représentant."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password"
        )

        self.folder = Folder.objects.create(name="Test Folder")
        self.entity = Entity.objects.create(name="Test Entity", folder=self.folder)
        self.representative = Representative.objects.create(
            name="Test Representative", entity=self.entity, folder=self.folder
        )
