"""Tests for gRPC client."""

import unittest
from unittest.mock import MagicMock, patch

from iterm_mcpy.grpc_client import ITermClient
from iterm_mcpy import iterm_mcp_pb2


class TestITermClient(unittest.TestCase):
    """Test gRPC client methods."""

    @patch('iterm_mcpy.grpc_client.grpc.insecure_channel')
    @patch('iterm_mcpy.grpc_client.iterm_mcp_pb2_grpc.ITermServiceStub')
    def setUp(self, mock_stub_class, mock_channel):
        self.mock_stub = mock_stub_class.return_value
        self.client = ITermClient()

    def test_list_sessions(self):
        """Test listing sessions."""
        mock_response = iterm_mcp_pb2.SessionList()
        session = mock_response.sessions.add()
        session.id = "test-id"
        session.name = "test-session"
        self.mock_stub.ListSessions.return_value = mock_response

        sessions = self.client.list_sessions()

        self.mock_stub.ListSessions.assert_called_once()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "test-id")

    def test_focus_session(self):
        """Test focusing a session."""
        mock_response = iterm_mcp_pb2.StatusResponse(success=True)
        self.mock_stub.FocusSession.return_value = mock_response

        result = self.client.focus_session("test-id")

        self.mock_stub.FocusSession.assert_called_once()
        args = self.mock_stub.FocusSession.call_args[0][0]
        self.assertEqual(args.identifier, "test-id")
        self.assertTrue(result)

    def test_set_active_session_by_agent(self):
        """Test setting active session by agent name."""
        mock_response = iterm_mcp_pb2.StatusResponse(success=True)
        self.mock_stub.SetActiveSession.return_value = mock_response

        result = self.client.set_active_session(agent="alice")

        self.mock_stub.SetActiveSession.assert_called_once()
        self.assertTrue(result)

    def test_create_sessions(self):
        """Test creating sessions with layout."""
        mock_response = iterm_mcp_pb2.CreateSessionsResponse()
        created = mock_response.sessions.add()
        created.session_id = "new-id"
        created.name = "Session1"
        mock_response.window_id = "window-123"
        self.mock_stub.CreateSessions.return_value = mock_response

        response = self.client.create_sessions(
            sessions=[{'name': 'Session1', 'agent': 'alice'}],
            layout='HORIZONTAL_SPLIT'
        )

        self.mock_stub.CreateSessions.assert_called_once()
        self.assertEqual(len(response.sessions), 1)
        self.assertEqual(response.window_id, "window-123")

    def test_write_to_sessions(self):
        """Test writing to multiple sessions."""
        mock_response = iterm_mcp_pb2.WriteToSessionsResponse()
        mock_response.sent_count = 2
        self.mock_stub.WriteToSessions.return_value = mock_response

        response = self.client.write_to_sessions(
            messages=[
                {'content': 'echo hello', 'targets': [{'name': 'Session1'}]},
                {'content': 'echo world', 'targets': [{'agent': 'alice'}]}
            ],
            parallel=True
        )

        self.mock_stub.WriteToSessions.assert_called_once()
        self.assertEqual(response.sent_count, 2)

    def test_read_sessions(self):
        """Test reading from multiple sessions."""
        mock_response = iterm_mcp_pb2.ReadSessionsResponse()
        output = mock_response.outputs.add()
        output.session_id = "session-1"
        output.content = "Hello World"
        mock_response.total_sessions = 1
        self.mock_stub.ReadSessions.return_value = mock_response

        response = self.client.read_sessions(
            targets=[{'name': 'Session1', 'max_lines': 50}]
        )

        self.mock_stub.ReadSessions.assert_called_once()
        self.assertEqual(response.total_sessions, 1)
        self.assertEqual(response.outputs[0].content, "Hello World")

    def test_register_agent(self):
        """Test registering an agent."""
        mock_response = iterm_mcp_pb2.Agent(
            name="alice",
            session_id="session-123"
        )
        self.mock_stub.RegisterAgent.return_value = mock_response

        agent = self.client.register_agent(
            name="alice",
            session_id="session-123",
            teams=["frontend"]
        )

        self.mock_stub.RegisterAgent.assert_called_once()
        self.assertEqual(agent.name, "alice")

    def test_list_agents(self):
        """Test listing agents."""
        mock_response = iterm_mcp_pb2.AgentList()
        agent = mock_response.agents.add()
        agent.name = "alice"
        agent.session_id = "s1"
        self.mock_stub.ListAgents.return_value = mock_response

        agents = self.client.list_agents()

        self.mock_stub.ListAgents.assert_called_once()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].name, "alice")

    def test_list_agents_filtered_by_team(self):
        """Test listing agents filtered by team."""
        mock_response = iterm_mcp_pb2.AgentList()
        self.mock_stub.ListAgents.return_value = mock_response

        self.client.list_agents(team="frontend")

        self.mock_stub.ListAgents.assert_called_once()
        args = self.mock_stub.ListAgents.call_args[0][0]
        self.assertEqual(args.team, "frontend")

    def test_create_team(self):
        """Test creating a team."""
        mock_response = iterm_mcp_pb2.Team(
            name="frontend",
            description="Frontend team"
        )
        self.mock_stub.CreateTeam.return_value = mock_response

        team = self.client.create_team(
            name="frontend",
            description="Frontend team"
        )

        self.mock_stub.CreateTeam.assert_called_once()
        self.assertEqual(team.name, "frontend")

    def test_list_teams(self):
        """Test listing teams."""
        mock_response = iterm_mcp_pb2.TeamList()
        team = mock_response.teams.add()
        team.name = "engineering"
        self.mock_stub.ListTeams.return_value = mock_response

        teams = self.client.list_teams()

        self.mock_stub.ListTeams.assert_called_once()
        self.assertEqual(len(teams), 1)
        self.assertEqual(teams[0].name, "engineering")

    def test_assign_agent_to_team(self):
        """Test assigning agent to team."""
        mock_response = iterm_mcp_pb2.StatusResponse(success=True)
        self.mock_stub.AssignAgentToTeam.return_value = mock_response

        result = self.client.assign_agent_to_team("alice", "frontend")

        self.mock_stub.AssignAgentToTeam.assert_called_once()
        args = self.mock_stub.AssignAgentToTeam.call_args[0][0]
        self.assertEqual(args.agent_name, "alice")
        self.assertEqual(args.team_name, "frontend")
        self.assertTrue(result)

    def test_send_cascade_message(self):
        """Test sending cascade message."""
        mock_response = iterm_mcp_pb2.CascadeMessageResponse()
        mock_response.delivered_count = 3
        mock_response.skipped_count = 1
        self.mock_stub.SendCascadeMessage.return_value = mock_response

        response = self.client.send_cascade_message(
            broadcast="Hello everyone!",
            teams={"frontend": "Frontend specific"},
            agents={"alice": "Alice specific"}
        )

        self.mock_stub.SendCascadeMessage.assert_called_once()
        self.assertEqual(response.delivered_count, 3)
        self.assertEqual(response.skipped_count, 1)

    # ==================== Backward Compatibility Tests ====================

    def test_write_to_terminal_backward_compat(self):
        """Test backward compatible write_to_terminal method."""
        mock_response = iterm_mcp_pb2.WriteToSessionsResponse()
        mock_response.sent_count = 1
        self.mock_stub.WriteToSessions.return_value = mock_response

        result = self.client.write_to_terminal("Session1", "ls -la")

        self.mock_stub.WriteToSessions.assert_called_once()
        self.assertTrue(result)

    def test_read_terminal_output_backward_compat(self):
        """Test backward compatible read_terminal_output method."""
        mock_response = iterm_mcp_pb2.ReadSessionsResponse()
        output = mock_response.outputs.add()
        output.content = "file1\nfile2\n"
        self.mock_stub.ReadSessions.return_value = mock_response

        result = self.client.read_terminal_output("Session1", max_lines=50)

        self.mock_stub.ReadSessions.assert_called_once()
        self.assertEqual(result, "file1\nfile2\n")


class TestITermClientContextManager(unittest.TestCase):
    """Test context manager behavior."""

    @patch('iterm_mcpy.grpc_client.grpc.insecure_channel')
    @patch('iterm_mcpy.grpc_client.iterm_mcp_pb2_grpc.ITermServiceStub')
    def test_context_manager(self, mock_stub_class, mock_channel):
        """Test client as context manager."""
        with ITermClient() as client:
            self.assertIsInstance(client, ITermClient)

        mock_channel.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
