import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from iterm_mcpy.grpc_server import ITermService
    from protos import iterm_mcp_pb2
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

class TestGRPCSmoke(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if not GRPC_AVAILABLE:
            self.skipTest("gRPC dependencies not installed")

    def test_service_instantiation(self):
        """Test that the ITermService can be instantiated."""
        service = ITermService()
        self.assertIsNotNone(service)
        self.assertIsNone(service.terminal)

    @patch('iterm_mcpy.grpc_server.iterm2')
    async def test_list_sessions_empty(self, mock_iterm2):
        """Test ListSessions with mocked dependencies."""
        service = ITermService()
        # Mock initialize to return True
        service.initialize = AsyncMock(return_value=True)
        # Mock terminal sessions
        service.terminal = MagicMock()
        service.terminal.sessions = {}
        
        response = await service.ListSessions(iterm_mcp_pb2.Empty(), MagicMock())
        self.assertIsInstance(response, iterm_mcp_pb2.SessionList)
        self.assertEqual(len(response.sessions), 0)

if __name__ == '__main__':
    unittest.main()
