"""
Integration tests for agent API endpoints.
"""

import pytest
from app import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_agent_chat_endpoint(client):
    """Test the agent chat endpoint."""
    response = client.post('/api/agent/chat', json={
        'query': 'What are human rights?',
        'topic': 'foundational_rights',
        'difficulty': 'beginner'
    })
    
    assert response.status_code == 200
    data = response.json
    
    assert 'answer' in data
    assert 'confidence' in data
    assert 'tools_used' in data
    assert 'sources' in data


def test_agent_chat_debug_mode(client):
    """Test agent chat in debug mode."""
    response = client.post('/api/agent/chat', json={
        'query': 'Explain freedom of expression',
        'topic': 'freedom_expression',
        'mode': 'debug'
    })
    
    assert response.status_code == 200
    data = response.json
    
    assert 'reasoning_trace' in data
    assert len(data['reasoning_trace']) > 0


def test_agent_chat_missing_query(client):
    """Test agent chat with missing query."""
    response = client.post('/api/agent/chat', json={
        'topic': 'foundational_rights'
    })
    
    assert response.status_code == 400
    assert 'error' in response.json


def test_agent_tools_endpoint(client):
    """Test the tools listing endpoint."""
    response = client.get('/api/agent/tools')
    
    assert response.status_code == 200
    data = response.json
    
    assert 'tools' in data
    assert len(data['tools']) == 4


def test_agent_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get('/api/agent/health')
    
    assert response.status_code == 200
    data = response.json
    
    assert data['status'] == 'healthy'
    assert data['agent_initialized'] is True
    assert data['tools_available'] == 4