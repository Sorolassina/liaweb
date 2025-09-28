"""
Configuration globale pour pytest
"""
import pytest
import asyncio
from typing import Generator
from app_lia_web.core.database import get_session
from app_lia_web.app.models.base import User, Programme
from app_lia_web.app.models.enums import UserRole



@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_session() -> Generator:
    """Create a test database session using the application's get_session."""
    # Utilisation de la fonction get_session de l'application
    # pour être cohérent avec la configuration de production
    session_generator = get_session()
    session = next(session_generator) #Recupère la session de la base de données
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user(test_session) -> User:
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        nom_complet="Test User",
        mot_de_passe_hash="hashed_password",
        role=UserRole.CONSEILLER,
        actif=True
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def sample_programme(test_session) -> Programme:
    """Create a sample programme for testing."""
    programme = Programme(
        nom="Test Programme",
        description="Programme de test",
        duree_mois=12,
        actif=True
    )
    test_session.add(programme)
    test_session.commit()
    test_session.refresh(programme)
    return programme


@pytest.fixture
def mock_session():
    """Mock session for testing without database."""
    class MockSession:
        def __init__(self):
            self.executed_queries = []
            self.mock_results = {}
        
        def execute(self, query, params=None):
            self.executed_queries.append((query, params))
            # Retourner des résultats mockés selon le type de requête
            query_str = str(query)
            if "schema_name" in query_str and "schemata" in query_str:
                # Mock pour get_all_program_schemas
                return MockResult([["acd"], ["aci"], ["act"]])
            elif "EXISTS" in query_str and "preinscription" in query_str:
                # Mock pour schema_has_table
                schema = params.get("schema", "") if params else ""
                return MockResult([[schema in ["acd", "aci"]]])  # Seuls acd et aci ont preinscription
            elif "COUNT(*)" in query_str and "preinscription" in query_str:
                # Mock pour get_total_count
                return MockResult([[5]])  # 5 préinscriptions
            else:
                return MockResult([[]])
    
    class MockResult:
        def __init__(self, data):
            self.data = data
            self.index = 0
        
        def fetchall(self):
            return [MockRow(row) for row in self.data]
        
        def fetchone(self):
            if self.index < len(self.data):
                row = MockRow(self.data[self.index])
                self.index += 1
                return row
            return None
    
    class MockRow:
        def __init__(self, data):
            self.data = data
        
        def __getitem__(self, index):
            return self.data[index]
    
    return MockSession()
