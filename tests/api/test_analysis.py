import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.endpoints.analysis import get_indicators, get_tokens, get_token_market_info
from tests.conftest import MockRow


class TestIndicatorsAPI:
    """Test cases for the /analysis/indicators endpoint"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock(spec=Session)
        return db

    @patch('app.api.endpoints.analysis.text')
    def test_get_indicators_success(
        self, 
        mock_text, 
        mock_db, 
        mock_result_rows
    ):
        """Test successful retrieval of indicators"""
        # Setup mocks - replace tables with actual dict
        mock_tables_dict = {
            'f5m': 'test_schema.f_coin_signal_5m',
            'f30m': 'test_schema.f_coin_signal_30m',
            'f1h': 'test_schema.f_coin_signal_1h',
            'f4h': 'test_schema.f_coin_signal_4h',
            'f1d': 'test_schema.f_coin_signal_1d',
        }
        # Replace the mock with the actual dict
        import app.api.endpoints.analysis as analysis_module
        with patch.object(analysis_module, 'tables', mock_tables_dict):
            mock_query = Mock()
            mock_text.return_value = mock_query
            mock_execute = Mock()
            mock_execute.fetchall.return_value = mock_result_rows
            mock_db.execute.return_value = mock_execute

            # Call the function
            result = get_indicators(
                pair="USDM_ADA",
                timeframe="1h",
                limit=100,
                db=mock_db
            )

            # Assertions - use fixture data instead of hardcoded values
            assert result.pair == "USDM/ADA"
            assert result.timeframe == "1h"
            assert len(result.data) == 2
            # Compare with first row from fixture
            row = None
            for i in range(len(result.data)):
                if result.data[i].timestamp == mock_result_rows[1].timestamp:
                    row = result.data[i]
                    break
            assert row is not None
            assert row.timestamp == mock_result_rows[1].timestamp
            assert row.open == round(mock_result_rows[1].open, 6)
            assert row.high == round(mock_result_rows[1].high, 6)
            assert row.low == round(mock_result_rows[1].low, 6)
            assert row.close == round(mock_result_rows[1].close, 6)
            assert row.volume == round(mock_result_rows[1].volume, 6)
            assert row.rsi7 == round(mock_result_rows[1].rsi7, 6)
            assert row.rsi14 == round(mock_result_rows[1].rsi14, 6)
            assert row.adx14 == round(mock_result_rows[1].adx14, 6)
            assert row.psar == round(mock_result_rows[1].psar, 6)

    def test_get_indicators_invalid_timeframe(self, mock_db):
        """Test error handling for invalid timeframe"""
        with pytest.raises(HTTPException) as exc_info:
            get_indicators(
                pair="USDM_ADA",
                timeframe="invalid",
                db=mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid timeframe" in exc_info.value.detail

    @patch('app.api.endpoints.analysis.text')
    def test_get_indicators_no_data_found(
        self, 
        mock_text, 
        mock_db
    ):
        """Test error handling when no data is found"""
        # Setup mocks
        mock_tables_dict = {'f1h': 'test_schema.f_coin_signal_1h'}
        import app.api.endpoints.analysis as analysis_module
        with patch.object(analysis_module, 'tables', mock_tables_dict):
            mock_query = Mock()
            mock_text.return_value = mock_query
            mock_execute = Mock()
            mock_execute.fetchall.return_value = []
            mock_db.execute.return_value = mock_execute

            with pytest.raises(HTTPException) as exc_info:
                get_indicators(
                    pair="USDM_ADA",
                    timeframe="1h",
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "No data found" in exc_info.value.detail


class TestTokensAPI:
    """Test cases for the /analysis/tokens endpoint"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock(spec=Session)
        return db

    def test_get_tokens_success(self, mock_db, mock_tokens):
        """Test successful retrieval of tokens"""
        # Setup mocks
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_tokens
        mock_db.query.return_value = mock_query

        # Call the function
        result = get_tokens(db=mock_db)

        # Assertions
        assert len(result) == len(mock_tokens)
        assert result[0].id == mock_tokens[0].id
        assert result[0].name == mock_tokens[0].name
        assert result[0].symbol == mock_tokens[0].symbol

    def test_get_tokens_with_search(self, mock_db, mock_tokens):
        """Test token search functionality"""
        filtered_tokens = [t for t in mock_tokens if "USD" in t.name.upper() or "USD" in t.symbol.upper()]
        
        # Setup mocks
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_tokens
        mock_db.query.return_value = mock_query

        # Call the function
        result = get_tokens(search="usd", db=mock_db)

        # Assertions
        assert len(result) == len(filtered_tokens)
        for token in result:
            assert "USD" in token.name.upper() or "USD" in token.symbol.upper()

    def test_get_tokens_with_limit(self, mock_db, mock_tokens):
        """Test token retrieval with limit"""
        limited_tokens = mock_tokens[:2]
        
        # Setup mocks
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = limited_tokens
        mock_db.query.return_value = mock_query

        # Call the function
        result = get_tokens(limit=2, db=mock_db)

        # Assertions
        assert len(result) == 2

    def test_get_tokens_with_offset(self, mock_db, mock_tokens):
        """Test token retrieval with offset"""
        offset_tokens = mock_tokens[1:]
        
        # Setup mocks
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = offset_tokens
        mock_db.query.return_value = mock_query

        # Call the function
        result = get_tokens(offset=1, db=mock_db)

        # Assertions
        assert len(result) == len(offset_tokens)

    def test_get_tokens_endpoint_success(self, client, mock_tokens):
        """Test HTTP request to GET /analysis/tokens endpoint"""
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_tokens
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get("/analysis/tokens")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(mock_tokens)

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_tokens_endpoint_with_search(self, client, mock_tokens):
        """Test HTTP request with search parameter"""
        filtered_tokens = [t for t in mock_tokens if "USD" in t.name.upper() or "USD" in t.symbol.upper()]
        
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_tokens
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get(
            "/analysis/tokens",
            params={"search": "usd"}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(filtered_tokens)

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_tokens_endpoint_with_limit(self, client, mock_tokens):
        """Test HTTP request with limit parameter"""
        limited_tokens = mock_tokens[:2]
        
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = limited_tokens
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get(
            "/analysis/tokens",
            params={"limit": 2}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_tokens_endpoint_with_offset(self, client, mock_tokens):
        """Test HTTP request with offset parameter"""
        offset_tokens = mock_tokens[1:]
        
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = offset_tokens
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get(
            "/analysis/tokens",
            params={"offset": 1}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(offset_tokens)

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_tokens_endpoint_with_all_params(self, client, mock_tokens):
        """Test HTTP request with all parameters"""
        filtered_tokens = [t for t in mock_tokens if "USD" in t.name.upper() or "USD" in t.symbol.upper()]
        limited_tokens = filtered_tokens[:1]
        
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = limited_tokens
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get(
            "/analysis/tokens",
            params={
                "search": "usd",
                "limit": 1,
                "offset": 0
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_tokens_endpoint_empty_result(self, client):
        """Test HTTP request that returns no results"""
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Make HTTP request
        response = client.get(
            "/analysis/tokens",
            params={"search": "nonexistent"}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

        # Cleanup
        app.dependency_overrides.clear()


class TestTokenMarketInfoAPI:
    """Test cases for the GET /analysis/tokens/{symbol} endpoint"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_token_market_data(self):
        """Create mock token market data row matching the SQL query result"""
        return MockRow(
            id="addr1qxy99g3k...tokenaddress",
            name="USDM",
            symbol="USDM",
            price=50000.00,
            change_24h=-1.25,
            low_24h=49500.00,
            high_24h=51500.00,
            volume_24h=982345000.00
        )

    @patch('app.api.endpoints.analysis.text')
    @patch('app.api.endpoints.analysis.datetime')
    def test_get_token_market_info_success(
        self,
        mock_datetime,
        mock_text,
        mock_db,
        mock_token_market_data
    ):
        """Test successful retrieval of token market info"""
        # Mock datetime.now() to return a fixed timestamp
        from datetime import datetime as dt
        fixed_time = dt(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time
        
        # Setup mocks
        mock_query = Mock()
        mock_text.return_value = mock_query
        mock_execute = Mock()
        mock_execute.fetchone.return_value = mock_token_market_data
        mock_db.execute.return_value = mock_execute

        # Call the function
        result = get_token_market_info(
            symbol="USDM",
            db=mock_db
        )

        # Assertions
        assert result.id == "addr1qxy99g3k...tokenaddress"
        assert result.name == "USDM"
        assert result.symbol == "USDM"
        assert result.price == 50000.00
        assert result.change_24h == -1.25
        assert result.low_24h == 49500.00
        assert result.high_24h == 51500.00
        assert result.volume_24h == 982345000.00

        # Verify the query was executed
        assert mock_db.execute.called
        mock_text.assert_called_once()

    @patch('app.api.endpoints.analysis.text')
    @patch('app.api.endpoints.analysis.datetime')
    def test_get_token_market_info_not_found(
        self,
        mock_datetime,
        mock_text,
        mock_db
    ):
        """Test error handling when token is not found"""
        # Mock datetime.now()
        from datetime import datetime as dt
        fixed_time = dt(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time
        
        # Setup mocks - return None (no token found)
        mock_query = Mock()
        mock_text.return_value = mock_query
        mock_execute = Mock()
        mock_execute.fetchone.return_value = None
        mock_db.execute.return_value = mock_execute

        # Call the function and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_token_market_info(
                symbol="NONEXISTENT",
                db=mock_db
            )
        
        assert exc_info.value.status_code == 404
        assert "Token not found" in exc_info.value.detail

    @patch('app.api.endpoints.analysis.text')
    @patch('app.api.endpoints.analysis.datetime')
    def test_get_token_market_info_with_null_values(
        self,
        mock_datetime,
        mock_text,
        mock_db
    ):
        """Test handling of null values in market data"""
        # Mock datetime.now()
        from datetime import datetime as dt
        fixed_time = dt(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time
        
        # Mock row with some null values
        mock_row = MockRow(
            id="addr1qxy99g3k...tokenaddress",
            name="USDM",
            symbol="USDM",
            price=None,
            change_24h=None,
            low_24h=None,
            high_24h=None,
            volume_24h=None
        )
        
        # Setup mocks
        mock_query = Mock()
        mock_text.return_value = mock_query
        mock_execute = Mock()
        mock_execute.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_execute

        # Call the function
        result = get_token_market_info(
            symbol="USDM",
            db=mock_db
        )

        # Assertions - null values should default to 0.0
        assert result.id == "addr1qxy99g3k...tokenaddress"
        assert result.name == "USDM"
        assert result.symbol == "USDM"
        assert result.price == 0.0
        assert result.change_24h == 0.0
        assert result.low_24h == 0.0
        assert result.high_24h == 0.0
        assert result.volume_24h == 0.0

    @patch('app.api.endpoints.analysis.text')
    @patch('app.api.endpoints.analysis.datetime')
    def test_get_token_market_info_symbol_case_insensitive(
        self,
        mock_datetime,
        mock_text,
        mock_db,
        mock_token_market_data
    ):
        """Test that symbol parameter is case-insensitive (converted to uppercase)"""
        # Mock datetime.now()
        from datetime import datetime as dt
        fixed_time = dt(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time
        
        # Setup mocks
        mock_query = Mock()
        mock_text.return_value = mock_query
        mock_execute = Mock()
        mock_execute.fetchone.return_value = mock_token_market_data
        mock_db.execute.return_value = mock_execute

        # Call the function with lowercase symbol
        result = get_token_market_info(
            symbol="usdm",
            db=mock_db
        )

        # Assertions - should work with lowercase input
        assert result.symbol == "USDM"
        
        # Verify the query was called (symbol should be uppercased in query)
        assert mock_db.execute.called

    def test_get_token_market_info_endpoint_success(self, client):
        """Test HTTP request to GET /analysis/tokens/{symbol} endpoint"""
        # Mock token market data
        mock_row = MockRow(
            id="addr1qxy99g3k...tokenaddress",
            name="USDM",
            symbol="USDM",
            price=50000.00,
            change_24h=-1.25,
            low_24h=49500.00,
            high_24h=51500.00,
            volume_24h=982345000.00
        )
        
        # Setup mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_execute = Mock()
        mock_execute.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_execute

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Mock datetime and text
        with patch('app.api.endpoints.analysis.datetime') as mock_dt, \
             patch('app.api.endpoints.analysis.text') as mock_text:
            from datetime import datetime as dt
            fixed_time = dt(2024, 1, 15, 12, 0, 0)
            mock_dt.now.return_value = fixed_time
            mock_text.return_value = mock_query

            # Make HTTP request
            response = client.get("/analysis/tokens/USDM")

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "addr1qxy99g3k...tokenaddress"
            assert data["name"] == "USDM"
            assert data["symbol"] == "USDM"
            assert data["price"] == 50000.00
            assert data["change_24h"] == -1.25
            assert data["low_24h"] == 49500.00
            assert data["high_24h"] == 51500.00
            assert data["volume_24h"] == 982345000.00

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_token_market_info_endpoint_not_found(self, client):
        """Test HTTP request when token is not found"""
        # Setup mock database - return None
        mock_db = Mock()
        mock_query = Mock()
        mock_execute = Mock()
        mock_execute.fetchone.return_value = None
        mock_db.execute.return_value = mock_execute

        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db

        from main import app
        app.dependency_overrides[get_db] = override_get_db

        # Mock datetime and text
        with patch('app.api.endpoints.analysis.datetime') as mock_dt, \
             patch('app.api.endpoints.analysis.text') as mock_text:
            from datetime import datetime as dt
            fixed_time = dt(2024, 1, 15, 12, 0, 0)
            mock_dt.now.return_value = fixed_time
            mock_text.return_value = mock_query

            # Make HTTP request
            response = client.get("/analysis/tokens/NONEXISTENT")

            # Assertions
            assert response.status_code == 404
            assert "Token not found" in response.json()["detail"]

        # Cleanup
        app.dependency_overrides.clear()


class TestSwapsAPI:
    """Test cases for the /analysis/swaps endpoints (TASK 6 & 7)"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_swaps(self):
        """Create mock swap objects for testing"""
        from app.models.swaps import Swap
        
        return [
            Swap(
                transaction_id="998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
                user_id="addr1qxy99g3k...useraddress",
                from_token="USDM",
                to_token="ADA",
                from_amount=0.1,
                to_amount=5000.00,
                price=50000.00,
                timestamp=1697123456,
                status="completed"
            ),
            Swap(
                transaction_id="a88f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060ec",
                user_id="addr1qxy99g3k...useraddress",
                from_token="ADA",
                to_token="USDM",
                from_amount=1000.0,
                to_amount=0.02,
                price=0.00002,
                timestamp=1697127056,
                status="completed"
            ),
            Swap(
                transaction_id="b99f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060ed",
                user_id="addr1qxy99g3k...otheruser",
                from_token="USDM",
                to_token="ADA",
                from_amount=0.2,
                to_amount=10000.00,
                price=50000.00,
                timestamp=1697130656,
                status="pending"
            ),
        ]

    @pytest.fixture
    def mock_user_id(self):
        """Mock user ID (wallet address) for authentication"""
        return "addr1qxy99g3k...useraddress"

    # ========== TASK 6: POST /analysis/swaps Tests ==========

    def test_create_swap_success(self, client, mock_db, mock_user_id):
        """Test successful creation of a swap transaction (TASK 6)"""
        from app.models.swaps import Swap
        from app.core.dependencies import get_current_user
        
        # Mock swap data
        swap_data = {
            "transaction_id": "998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
            "from_token": "USDM",
            "to_token": "ADA",
            "from_amount": 0.1,
            "to_amount": 5000.00,
            "price": 50000.00
        }
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # No existing swap
        mock_db.query.return_value = mock_query
        
        # Mock the new swap object
        new_swap = Swap(
            transaction_id=swap_data["transaction_id"],
            user_id=mock_user_id,
            from_token=swap_data["from_token"],
            to_token=swap_data["to_token"],
            from_amount=swap_data["from_amount"],
            to_amount=swap_data["to_amount"],
            price=swap_data["price"],
            timestamp=1697123456,
            status="completed"
        )
        new_swap.transaction_id = swap_data["transaction_id"]
        new_swap.status = "completed"
        
        # Override dependencies
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        def override_get_current_user():
            return mock_user_id
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        # Mock db.add, commit, refresh
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: setattr(obj, 'transaction_id', swap_data["transaction_id"]) or setattr(obj, 'status', 'completed'))
        
        # Make HTTP request
        response = client.post(
            "/analysis/swaps",
            json=swap_data,
            headers={"Authorization": "Bearer mock_token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == swap_data["transaction_id"]
        assert data["status"] == "completed"
        
        # Verify database operations
        assert mock_db.add.called
        assert mock_db.commit.called
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_create_swap_with_timestamp(self, client, mock_db, mock_user_id):
        """Test creating swap with explicit timestamp (TASK 6)"""
        from app.core.dependencies import get_current_user
        
        # Mock swap data with timestamp
        swap_data = {
            "transaction_id": "998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
            "from_token": "USDM",
            "to_token": "ADA",
            "from_amount": 0.1,
            "to_amount": 5000.00,
            "price": 50000.00,
            "timestamp": 1697123456
        }
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Override dependencies
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        def override_get_current_user():
            return mock_user_id
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        # Mock db operations
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: setattr(obj, 'transaction_id', swap_data["transaction_id"]) or setattr(obj, 'status', 'completed'))
        
        # Make HTTP request
        response = client.post(
            "/analysis/swaps",
            json=swap_data,
            headers={"Authorization": "Bearer mock_token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == swap_data["transaction_id"]
        assert data["status"] == "completed"
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_create_swap_duplicate_transaction_id(self, client, mock_db, mock_user_id):
        """Test error when creating swap with duplicate transaction_id (TASK 6)"""
        from app.models.swaps import Swap
        from app.core.dependencies import get_current_user
        
        # Mock swap data
        swap_data = {
            "transaction_id": "998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
            "from_token": "USDM",
            "to_token": "ADA",
            "from_amount": 0.1,
            "to_amount": 5000.00,
            "price": 50000.00
        }
        
        # Mock existing swap
        existing_swap = Swap(
            transaction_id=swap_data["transaction_id"],
            user_id=mock_user_id,
            from_token="USDM",
            to_token="ADA",
            from_amount=0.1,
            to_amount=5000.00,
            price=50000.00,
            timestamp=1697123456,
            status="completed"
        )
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = existing_swap  # Existing swap found
        mock_db.query.return_value = mock_query
        
        # Override dependencies
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        def override_get_current_user():
            return mock_user_id
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        # Make HTTP request
        response = client.post(
            "/analysis/swaps",
            json=swap_data,
            headers={"Authorization": "Bearer mock_token"}
        )
        
        # Assertions
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_create_swap_missing_required_fields(self, client, mock_db, mock_user_id):
        """Test error when required fields are missing (TASK 6)"""
        from app.core.dependencies import get_current_user
        
        # Override dependencies
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        def override_get_current_user():
            return mock_user_id
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        # Test missing transaction_id
        response = client.post(
            "/analysis/swaps",
            json={
                "from_token": "USDM",
                "to_token": "ADA",
                "from_amount": 0.1,
                "to_amount": 5000.00,
                "price": 50000.00
            },
            headers={"Authorization": "Bearer mock_token"}
        )
        assert response.status_code == 422  # Validation error
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_create_swap_unauthorized(self, client, mock_db):
        """Test that POST /analysis/swaps requires authentication (TASK 6)"""
        # Override get_db only
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make request without Authorization header
        response = client.post(
            "/analysis/swaps",
            json={
                "transaction_id": "998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
                "from_token": "USDM",
                "to_token": "ADA",
                "from_amount": 0.1,
                "to_amount": 5000.00,
                "price": 50000.00
            }
        )
        # Should return 401 or 422 (depending on FastAPI validation)
        assert response.status_code in [401, 422]
        
        # Cleanup
        app.dependency_overrides.clear()

    # ========== TASK 7: GET /analysis/swaps Tests ==========

    def test_get_swaps_success_default_pagination(self, client, mock_db, mock_swaps):
        """Test successful retrieval of swaps with default pagination (TASK 7)"""
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(mock_swaps)
        mock_query.all.return_value = mock_swaps[:20]  # Default limit is 20
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get("/analysis/swaps")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["total"] == len(mock_swaps)
        assert len(data["transactions"]) <= 20
        
        # Verify transaction structure
        if data["transactions"]:
            transaction = data["transactions"][0]
            assert "transaction_id" in transaction
            assert "from_token" in transaction
            assert "to_token" in transaction
            assert "from_amount" in transaction
            assert "to_amount" in transaction
            assert "price" in transaction
            assert "timestamp" in transaction
            assert "status" in transaction
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_custom_pagination(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps with custom page and limit (TASK 7)"""
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(mock_swaps)
        mock_query.all.return_value = mock_swaps[:2]  # Limit 2
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get("/analysis/swaps?page=1&limit=2")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 2
        assert len(data["transactions"]) <= 2
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_from_token_filter(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps filtered by from_token (TASK 7)"""
        # Filter swaps by from_token
        filtered_swaps = [s for s in mock_swaps if "USDM" in s.from_token]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get("/analysis/swaps?from_token=USDM")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == len(filtered_swaps)
        for transaction in data["transactions"]:
            assert "USDM" in transaction["from_token"]
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_to_token_filter(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps filtered by to_token (TASK 7)"""
        # Filter swaps by to_token
        filtered_swaps = [s for s in mock_swaps if "ADA" in s.to_token]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get("/analysis/swaps?to_token=ADA")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == len(filtered_swaps)
        for transaction in data["transactions"]:
            assert "ADA" in transaction["to_token"]
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_time_filters(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps filtered by from_time and to_time (TASK 7)"""
        # Filter swaps by time range
        from_time = 1697123456
        to_time = 1697130656
        filtered_swaps = [s for s in mock_swaps if from_time <= s.timestamp <= to_time]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get(f"/analysis/swaps?from_time={from_time}&to_time={to_time}")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == len(filtered_swaps)
        for transaction in data["transactions"]:
            assert from_time <= transaction["timestamp"] <= to_time
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_user_id_filter(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps filtered by user_id (TASK 7)"""
        # Filter swaps by user_id
        user_id = "addr1qxy99g3k...useraddress"
        filtered_swaps = [s for s in mock_swaps if s.user_id == user_id]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get(f"/analysis/swaps?user_id={user_id}")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == len(filtered_swaps)
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_with_all_filters(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps with all filters combined (TASK 7)"""
        # Filter swaps by multiple criteria
        filtered_swaps = [
            s for s in mock_swaps 
            if "USDM" in s.from_token 
            and "ADA" in s.to_token
            and s.timestamp >= 1697123456
            and s.timestamp <= 1697130656
        ]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get(
            "/analysis/swaps",
            params={
                "page": 1,
                "limit": 20,
                "from_token": "USDM",
                "to_token": "ADA",
                "from_time": 1697123456,
                "to_time": 1697130656
            }
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 20
        assert len(data["transactions"]) == len(filtered_swaps)
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_empty_result(self, client, mock_db):
        """Test GET /analysis/swaps when no swaps are found (TASK 7)"""
        # Setup mock database - return empty list
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request
        response = client.get("/analysis/swaps")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["transactions"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 20
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_invalid_pagination(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps with invalid pagination parameters (TASK 7)"""
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(mock_swaps)
        mock_query.all.return_value = mock_swaps[:20]
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Test with page=0 (should default to 1)
        response = client.get("/analysis/swaps?page=0&limit=-1")
        
        # Assertions - should handle invalid values gracefully
        assert response.status_code == 200
        data = response.json()
        assert data["page"] >= 1
        assert data["limit"] >= 1
        
        # Test with limit > 100 (should cap at 100)
        response = client.get("/analysis/swaps?limit=200")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] <= 100
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_get_swaps_example_request(self, client, mock_db, mock_swaps):
        """Test GET /analysis/swaps matching the example request from task (TASK 7)"""
        # Filter swaps matching the example
        filtered_swaps = [s for s in mock_swaps if "USDM" in s.from_token]
        
        # Setup mock database
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = len(filtered_swaps)
        mock_query.all.return_value = filtered_swaps
        mock_db.query.return_value = mock_query
        
        # Override get_db dependency
        from app.db.session import get_db
        def override_get_db():
            yield mock_db
        
        from main import app
        app.dependency_overrides[get_db] = override_get_db
        
        # Make HTTP request matching example: GET /analysis/swaps?page=1&limit=20&from_token=USDM
        response = client.get("/analysis/swaps?page=1&limit=20&from_token=USDM")
        
        # Assertions matching example response structure
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 20
        
        # Verify transaction structure matches example
        if data["transactions"]:
            transaction = data["transactions"][0]
            assert "transaction_id" in transaction
            assert "from_token" in transaction
            assert "from_amount" in transaction
            assert "to_token" in transaction
            assert "to_amount" in transaction
            assert "price" in transaction
            assert "timestamp" in transaction
            assert "status" in transaction
        
        # Cleanup
        app.dependency_overrides.clear()