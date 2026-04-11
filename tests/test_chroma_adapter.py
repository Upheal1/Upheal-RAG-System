import pytest
from unittest.mock import MagicMock, patch

from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase, _build_where_filter
from services.shared.schemas import UserContext

@pytest.fixture
def mock_kb():
    # We patch _ensure_loaded to prevent any real local imports or connections
    with patch.object(ChromaKnowledgeBase, "_ensure_loaded"):
        kb = ChromaKnowledgeBase()
        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_embedding
        
        mock_col = MagicMock()
        kb._model = mock_model
        kb._collection = mock_col
        yield kb

def test_build_where_filter():
    ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 2})
    w = _build_where_filter(ctx)
    assert w == {"$or": [{"tag_primary": "anxiety"}, {"tag_primary": "general"}]}

    ctx_empty = UserContext(user_id="2", timestamp="now", form_scores={"suicidal": 1})
    assert _build_where_filter(ctx_empty) is None

def test_retrieve_tasks(mock_kb):
    mock_kb._collection.query.return_value = {
        "ids": [["kb_1", "kb_2"]],
        "documents": [["Manage excessive worry", "Maintain routine"]],
        "metadatas": [
            [
                {"tag_primary": "anxiety", "difficulty": 3, "clinical_tags": "anxiety, sleep"}, 
                {"tag_primary": "general", "difficulty": 2, "clinical_tags": "general"}
            ]
        ],
        "distances": [[0.1, 0.5]]
    }
    
    ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 2})
    
    tasks = mock_kb.retrieve_tasks(ctx, top_k=2)
    assert len(tasks) == 2
    
    # Task 1 asserts
    assert tasks[0].task_id == "kb_1"
    assert "anxiety" in tasks[0].symptom_tags
    assert "sleep" in tasks[0].symptom_tags
    assert tasks[0].difficulty == 3
    assert tasks[0].metadata["tag_primary"] == "anxiety"

    # Task 2 asserts
    assert tasks[1].task_id == "kb_2"
    assert tasks[1].symptom_tags == ["general"]
    assert tasks[1].difficulty == 2
    
    # Ensure query was actually called
    assert mock_kb._collection.query.called

def test_is_healthy(mock_kb):
    mock_kb._collection.count.return_value = 10
    assert mock_kb.is_healthy() is True
    
    mock_kb._collection.count.side_effect = Exception("DB Down")
    assert mock_kb.is_healthy() is False
