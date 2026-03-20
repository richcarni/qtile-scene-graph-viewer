from libqtile.command.client import InteractiveCommandClient
from threading import Thread
from textual.app import App, ComposeResult
from textual.widgets import Tree, Static
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal
from textual import log
from enum import Enum, auto

class NodeState(Enum):
    # UNSET = auto()
    EXPANDED = auto()
    COLLAPSED = auto()

class SceneGraphApp(App):
    def compose(self) -> ComposeResult:
        with Horizontal():
            # Left side: tree
            self.widget0 = Tree("Scene Graph", id="scene_tree")
            yield self.widget0
            # Right side: details panel
            self.widget = Static("Select a node to see details", id="details")
            yield self.widget

    async def on_mount(self):
        self.widget0.styles.width="2fr"
        self.widget.styles.width="1fr"
        self.collapsed_nodes = set()
        self.node_states: dict[str, NodeState] = {}
        self.selected_node_id = None
        self._last_tree_data = None
        self.fetch_tree_data()
        self.set_interval(0.5, self.fetch_tree_data)

    def fetch_tree_data(self) -> None:
        def background_task():
            # This will run asyncio.run() in its own thread
            c = InteractiveCommandClient()
            tree_data = c.core.stacking_info()
            if tree_data == self._last_tree_data:
                return
            self._last_tree_data = tree_data
            window_data = c.windows()
            internal_window_data = c.internal_windows()
            self.call_from_thread(self.update_tree, tree_data, window_data, internal_window_data)

        # Start background thread
        thread = Thread(target=background_task, daemon=True)
        thread.start()

    def update_tree(self, tree_data: dict, window_data, internal_window_data):
        self._node_lookup = {}
        tree_widget: Tree = self.query_one(Tree)
        tree_widget.auto_expand = False
        # Remove all existing children under the root
        tree_widget.root.remove_children()
        tree_widget.root.expand()

        def insert(node: dict, parent: TreeNode):
            window = None
            if node.get('wid') is not None:
                window = next((w for w in window_data if w["id"] == node['wid']), None)
                if window is None:
                    window = next((w for w in internal_window_data if w["id"] == node['wid']), None)

            text = f"{node['type']}{'' if node['enabled'] else ' [✘]'}{'' if not node['name'] else f' ({node.get("name")})'}"

            node_id = node.get('id')
            assert(node_id is not None)
            state = self.node_states.get(node_id)

            if state == NodeState.COLLAPSED:
                new_node = parent.add(text, data=(node, window), expand=False)
            elif state == NodeState.EXPANDED:
                new_node = parent.add(text, data=(node, window), expand=True)
            else:
                if window is not None:
                    new_node = parent.add(text, data=(node, window), expand=False)
                    self.node_states[node_id] = NodeState.COLLAPSED
                else:
                    new_node = parent.add(text, data=(node, window), expand=True)
                    self.node_states[node_id] = NodeState.EXPANDED

            self._node_lookup[node_id] = new_node

            for child in node.get("children", []):
                insert(child, new_node)

        insert(tree_data, tree_widget.root)

        # Snapshot the ID now; restore selection after all mutation events settle
        target_id = self.selected_node_id
        if target_id in self._node_lookup:
            target_node = self._node_lookup[target_id]
            self.call_after_refresh(lambda: tree_widget.select_node(target_node))
        else:
            self.selected_node_id = None
            self.call_after_refresh(lambda: tree_widget.unselect())

        # Remove stale entries for nodes that no longer exist
        current_ids = set(self._node_lookup.keys())
        stale_ids = set(self.node_states.keys()) - current_ids
        for stale_id in stale_ids:
            del self.node_states[stale_id]

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted):
        details: Static = self.query_one("#details", Static)
        if event.node.data:
            node_data = event.node.data[0]
            self.selected_node_id = node_data["id"]
            window_data = event.node.data[1]
            text = (
                "[b]Node[/b]\n"
                f"  name: {node_data['name']}\n"
                f"  type: {node_data['type']}\n"
                f"  enabled: {node_data['enabled']}\n"
                f"  x: {node_data['x']}\n"
                f"  y: {node_data['y']}\n"
            )
            view_text = ''
            if node_data['wid']:
                view_text = (
                    "\n[b]View[/b]\n"
                    f"  name: {window_data.get('name', 'N/A')}\n"
                    f"  wm_class: {window_data.get('wm_class', 'N/A')}\n"
                    f"  wid: {node_data.get('wid', 'N/A')}\n"
                    f"  shell: {window_data.get('shell', 'N/A')}\n"
                    f"  x: {window_data.get('x', 'N/A')}\n"
                    f"  y: {window_data.get('y', 'N/A')}\n"
                    f"  width: {window_data.get('width', 'N/A')}\n"
                    f"  height: {window_data.get('height', 'N/A')}\n"
                )
            details.update(text + ('' if node_data['wid'] is None else view_text))
        else:
            details.update("No info")

    def on_tree_node_expanded(self, event: Tree.NodeExpanded):
        if not event.node.data:
            return

        node_id = event.node.data[0].get("id")
        if node_id:
            self.node_states[node_id] = NodeState.EXPANDED

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed):
        if not event.node.data:
            return

        node_id = event.node.data[0].get("id")
        if node_id:
            self.node_states[node_id] = NodeState.COLLAPSED


if __name__ == "__main__":
    SceneGraphApp().run()

