from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
import requests, base64, os
from plyer import filechooser

class BuilderApp(App):
    def build(self):
        self.files = []
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text='JOSCOM BUILDER', font_size=24, bold=True))
        self.token_input = TextInput(hint_text='Paste your ghp_ token here', password=True, multiline=False, size_hint_y=None, height=50)
        layout.add_widget(self.token_input)
        self.status = Label(text='Pick files, then Send to GitHub', size_hint_y=None, height=60)
        layout.add_widget(self.status)
        btn_pick = Button(text='1. SELECT FILES', size_hint_y=None, height=60)
        btn_pick.bind(on_press=self.pick_files)
        layout.add_widget(btn_pick)
        btn_send = Button(text='2. SEND TO GITHUB', size_hint_y=None, height=60)
        btn_send.bind(on_press=self.send_files)
        layout.add_widget(btn_send)
        btn_check = Button(text='3. CHECK BUILD', size_hint_y=None, height=60)
        btn_check.bind(on_press=self.check_build)
        layout.add_widget(btn_check)
        return layout
    def pick_files(self, instance):
        filechooser.open_file(on_selection=self.got_files, multiple=True)
    def got_files(self, selection):
        if selection:
            self.files = selection
            self.status.text = f"Picked {len(selection)} files"
    def send_files(self, instance):
        token = self.token_input.text.strip()
        if not token or not self.files:
            self.status.text = "Put token + pick files first!"
            return
        self.status.text = "Sending..."
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        owner = "josephmasumba69-beep"
        repo = "Joscom_builder_apk"
        for path in self.files:
            name = os.path.basename(path)
            with open(path, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{name}"
            r = requests.get(url, headers=headers)
            sha = r.json().get('sha') if r.status_code == 200 else None
            data = {"message": f"Upload {name}", "content": content}
            if sha:
                data["sha"] = sha
            requests.put(url, headers=headers, json=data)
        self.status.text = "Sent! GitHub is now building..."
    def check_build(self, instance):
        token = self.token_input.text.strip()
        headers = {"Authorization": f"token {token}"}
        r = requests.get("https://api.github.com/repos/josephmasumba69-beep/Joscom_builder_apk/actions/runs?per_page=1", headers=headers)
        if r.status_code == 200:
            run = r.json()['workflow_runs'][0]
            self.status.text = f"Build: {run['status']} - {run['conclusion']}"
        else:
            self.status.text = "Could not check. Check token."

BuilderApp().run()
