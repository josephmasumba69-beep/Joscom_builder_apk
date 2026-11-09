from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout

class JoscomApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        layout = MDBoxLayout(orientation="vertical", padding=20, spacing=20)
        label = MDLabel(
            text="Welcome to JoscomApp\nBuilt by Joscom Masvic",
            halign="center",
            font_style="H5"
        )
        btn = MDRaisedButton(
            text="Click Me",
            pos_hint={"center_x": 0.5},
            on_release=self.on_click
        )
        layout.add_widget(label)
        layout.add_widget(btn)
        self.label = label
        return layout

    def on_click(self, *args):
        self.label.text = "You clicked! APK Works!"

if __name__ == "__main__":
    JoscomApp().run()
