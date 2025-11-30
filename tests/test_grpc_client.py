import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from iterm_mcpy.grpc_client import ITermClient
from protos import iterm_mcp_pb2

class TestITermClient(unittest.TestCase):
    @patch('iterm_mcpy.grpc_client.grpc.insecure_channel')
    @patch('iterm_mcpy.grpc_client.iterm_mcp_pb2_grpc.ITermServiceStub')
    def setUp(self, mock_stub_class, mock_channel):
        self.mock_stub = mock_stub_class.return_value
        self.client = ITermClient()

    def test_list_sessions(self):
        # Setup mock response
        mock_response = iterm_mcp_pb2.SessionList()
        session = mock_response.sessions.add()
        session.id = "test-id"
        session.name = "test-session"
        self.mock_stub.ListSessions.return_value = mock_response

        # Call method
        sessions = self.client.list_sessions()

        # Verify
        self.mock_stub.ListSessions.assert_called_once()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "test-id")

    def test_focus_session(self):
        mock_response = iterm_mcp_pb2.StatusResponse(success=True)
        self.mock_stub.FocusSession.return_value = mock_response

        result = self.client.focus_session("test-id")

        self.mock_stub.FocusSession.assert_called_once()
        args = self.mock_stub.FocusSession.call_args[0][0]
        self.assertEqual(args.identifier, "test-id")
        self.assertTrue(result)

    def test_write_to_terminal(self):
        mock_response = iterm_mcp_pb2.StatusResponse(success=True)
        self.mock_stub.WriteToTerminal.return_value = mock_response

        result = self.client.write_to_terminal("test-id", "ls -la", wait_for_prompt=True)

        self.mock_stub.WriteToTerminal.assert_called_once()
        args = self.mock_stub.WriteToTerminal.call_args[0][0]
        self.assertEqual(args.session_identifier, "test-id")
        self.assertEqual(args.command, "ls -la")
        self.assertTrue(args.wait_for_prompt)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
