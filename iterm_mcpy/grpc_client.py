import grpc
from protos import iterm_mcp_pb2
from protos import iterm_mcp_pb2_grpc
from typing import List, Optional

class ITermClient:
    def __init__(self, host: str = 'localhost', port: int = 50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = iterm_mcp_pb2_grpc.ITermServiceStub(self.channel)

    def list_sessions(self) -> List[iterm_mcp_pb2.Session]:
        response = self.stub.ListSessions(iterm_mcp_pb2.Empty())
        return response.sessions

    def focus_session(self, identifier: str) -> bool:
        response = self.stub.FocusSession(iterm_mcp_pb2.SessionIdentifier(identifier=identifier))
        return response.success

    def create_layout(self, layout_type: str, session_names: List[str]) -> List[iterm_mcp_pb2.Session]:
        request = iterm_mcp_pb2.CreateLayoutRequest(
            layout_type=layout_type,
            session_names=session_names
        )
        response = self.stub.CreateLayout(request)
        return response.sessions

    def write_to_terminal(self, session_identifier: str, command: str, wait_for_prompt: bool = False) -> bool:
        request = iterm_mcp_pb2.WriteRequest(
            session_identifier=session_identifier,
            command=command,
            wait_for_prompt=wait_for_prompt
        )
        response = self.stub.WriteToTerminal(request)
        return response.success

    def read_terminal_output(self, session_identifier: str, max_lines: int = 100) -> str:
        request = iterm_mcp_pb2.ReadOutputRequest(
            session_identifier=session_identifier,
            max_lines=max_lines
        )
        response = self.stub.ReadTerminalOutput(request)
        return response.output

    def send_control_character(self, session_identifier: str, control_char: str) -> bool:
        request = iterm_mcp_pb2.ControlCharRequest(
            session_identifier=session_identifier,
            control_char=control_char
        )
        response = self.stub.SendControlCharacter(request)
        return response.success

    def check_session_status(self, identifier: str) -> iterm_mcp_pb2.SessionStatus:
        return self.stub.CheckSessionStatus(iterm_mcp_pb2.SessionIdentifier(identifier=identifier))
