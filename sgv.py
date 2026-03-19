from libqtile.command.client import InteractiveCommandClient
from threading import Thread
from textual.app import App, ComposeResult
from textual.widgets import Tree, Static
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal
from textual import log

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
        tree_widget: Tree = self.query_one(Tree)

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

            new_node = parent.add(text, data=(node, window), expand=True)

            node_id = node.get('id');
            if node_id in self.collapsed_nodes:
                new_node.collapse()
            else:
                new_node.expand()

            for child in node.get("children", []):
                insert(child, new_node)

        insert(tree_data, tree_widget.root)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted):
        details: Static = self.query_one("#details", Static)
        if event.node.data:
            node_data = event.node.data[0]
            window_data = event.node.data[1]
            log(window_data)
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
            self.collapsed_nodes.discard(node_id)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed):
        if not event.node.data:
            return
        node_id = event.node.data[0].get("id")
        if node_id:
            self.collapsed_nodes.add(node_id)

if __name__ == "__main__":
    SceneGraphApp().run()

