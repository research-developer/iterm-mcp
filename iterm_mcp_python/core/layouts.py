"""Predefined layouts for iTerm2 terminal sessions."""

import asyncio
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .terminal import ItermTerminal

class LayoutType(Enum):
    """Types of predefined layouts."""
    
    SINGLE = "single"  # Single pane
    HORIZONTAL_SPLIT = "horizontal_split"  # Two panes side by side
    VERTICAL_SPLIT = "vertical_split"  # Two panes stacked
    QUAD = "quad"  # Four panes in a grid
    TRIPLE_RIGHT = "triple_right"  # Three panes with one on left and two on right
    TRIPLE_BOTTOM = "triple_bottom"  # Three panes with two on top and one on bottom


class LayoutManager:
    """Manages predefined layouts for iTerm2 sessions."""
    
    def __init__(self, terminal: ItermTerminal):
        """Initialize the layout manager.
        
        Args:
            terminal: The iTerm terminal manager
        """
        self.terminal = terminal
    
    async def create_layout(
        self,
        layout_type: LayoutType,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a layout with the specified configuration.
        
        Args:
            layout_type: The type of layout to create
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        method_name = f"_create_{layout_type.value}_layout"
        if not hasattr(self, method_name):
            raise ValueError(f"Unsupported layout type: {layout_type}")
            
        method = getattr(self, method_name)
        return await method(pane_names)
    
    async def _create_single_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a single pane layout.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Create a new window
        session = await self.terminal.create_window()
        
        # Set the pane name if provided
        name = "Main" if not pane_names or not pane_names[0] else pane_names[0]
        await session.set_name(name)
        
        return {name: session.id}
    
    async def _create_horizontal_split_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a horizontal split layout with two panes side by side.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Set default pane names if not provided
        if not pane_names or len(pane_names) < 2:
            pane_names = ["Left", "Right"]
        
        print(f"Creating horizontal split with panes: {pane_names}")
        
        # Create a new window for the first pane
        left_session = await self.terminal.create_window()
        await left_session.set_name(pane_names[0])
        print(f"Created left pane with name '{pane_names[0]}', actual name: '{left_session.name}'")
        
        # Create a split pane for the second pane
        right_session = await self.terminal.create_split_pane(
            left_session.id,
            vertical=True,
            name=pane_names[1]
        )
        
        print(f"Created right pane with name '{pane_names[1]}', actual name: '{right_session.name}'")
        
        # Force update both session names again
        await left_session.set_name(pane_names[0])
        await right_session.set_name(pane_names[1])
        
        print(f"After rename - Left pane: '{left_session.name}', Right pane: '{right_session.name}'")
        
        # Add a delay to allow the name to be set
        await asyncio.sleep(1)
        
        return {
            pane_names[0]: left_session.id,
            pane_names[1]: right_session.id
        }
    
    async def _create_vertical_split_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a vertical split layout with two panes stacked.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Set default pane names if not provided
        if not pane_names or len(pane_names) < 2:
            pane_names = ["Top", "Bottom"]
        
        # Create a new window for the first pane
        top_session = await self.terminal.create_window()
        await top_session.set_name(pane_names[0])
        
        # Create a split pane for the second pane
        bottom_session = await self.terminal.create_split_pane(
            top_session.id,
            vertical=False,
            name=pane_names[1]
        )
        
        return {
            pane_names[0]: top_session.id,
            pane_names[1]: bottom_session.id
        }
    
    async def _create_quad_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a quad layout with four panes in a grid.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Set default pane names if not provided
        if not pane_names or len(pane_names) < 4:
            pane_names = ["Top Left", "Top Right", "Bottom Left", "Bottom Right"]
        
        # Create a new window for the first pane
        top_left_session = await self.terminal.create_window()
        await top_left_session.set_name(pane_names[0])
        
        # Create a vertical split for the top right pane
        top_right_session = await self.terminal.create_split_pane(
            top_left_session.id,
            vertical=True,
            name=pane_names[1]
        )
        
        # Create a horizontal split for the bottom left pane
        bottom_left_session = await self.terminal.create_split_pane(
            top_left_session.id,
            vertical=False,
            name=pane_names[2]
        )
        
        # Create a horizontal split for the bottom right pane
        bottom_right_session = await self.terminal.create_split_pane(
            top_right_session.id,
            vertical=False,
            name=pane_names[3]
        )
        
        return {
            pane_names[0]: top_left_session.id,
            pane_names[1]: top_right_session.id,
            pane_names[2]: bottom_left_session.id,
            pane_names[3]: bottom_right_session.id
        }
    
    async def _create_triple_right_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a triple right layout with one pane on the left and two on the right.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Set default pane names if not provided
        if not pane_names or len(pane_names) < 3:
            pane_names = ["Left", "Top Right", "Bottom Right"]
        
        # Create a new window for the first pane
        left_session = await self.terminal.create_window()
        await left_session.set_name(pane_names[0])
        
        # Create a vertical split for the top right pane
        top_right_session = await self.terminal.create_split_pane(
            left_session.id,
            vertical=True,
            name=pane_names[1]
        )
        
        # Create a horizontal split for the bottom right pane
        bottom_right_session = await self.terminal.create_split_pane(
            top_right_session.id,
            vertical=False,
            name=pane_names[2]
        )
        
        return {
            pane_names[0]: left_session.id,
            pane_names[1]: top_right_session.id,
            pane_names[2]: bottom_right_session.id
        }
    
    async def _create_triple_bottom_layout(
        self,
        pane_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Create a triple bottom layout with two panes on top and one on the bottom.
        
        Args:
            pane_names: Optional list of names for the panes
            
        Returns:
            A dictionary mapping pane names to session IDs
        """
        # Set default pane names if not provided
        if not pane_names or len(pane_names) < 3:
            pane_names = ["Top Left", "Top Right", "Bottom"]
        
        # Create a new window for the first pane
        top_left_session = await self.terminal.create_window()
        await top_left_session.set_name(pane_names[0])
        
        # Create a vertical split for the top right pane
        top_right_session = await self.terminal.create_split_pane(
            top_left_session.id,
            vertical=True,
            name=pane_names[1]
        )
        
        # Create a horizontal split for the bottom pane (from top left)
        bottom_session = await self.terminal.create_split_pane(
            top_left_session.id,
            vertical=False,
            name=pane_names[2]
        )
        
        # Resize to make the bottom pane span the full width
        # Note: This may not work perfectly due to iTerm2 limitations
        
        return {
            pane_names[0]: top_left_session.id,
            pane_names[1]: top_right_session.id,
            pane_names[2]: bottom_session.id
        }