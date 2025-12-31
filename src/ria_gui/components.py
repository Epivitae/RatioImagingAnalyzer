# components.py
import tkinter as tk
from tkinter import ttk

class ToggledFrame(ttk.Frame):
    def __init__(self, parent, text="", *args, **options):
        # 默认使用 Card 样式，除非指定
        if "style" not in options:
            options["style"] = "Card.TFrame"
            
        ttk.Frame.__init__(self, parent, *args, **options)
        
        self.show = tk.IntVar()
        self.show.set(0)
        
        self.title_frame = ttk.Frame(self, style="Card.TFrame")
        self.title_frame.pack(fill="x", expand=1)
        
        self.toggle_btn = ttk.Checkbutton(
            self.title_frame, 
            width=2, 
            text='▶', 
            command=self.toggle, 
            variable=self.show, 
            style='Toolbutton'
        )
        self.toggle_btn.pack(side="left")
        
        self.lbl_title = ttk.Label(self.title_frame, text=text, style="Blue.TLabel")
        self.lbl_title.pack(side="left", padx=5)
        
        self.sub_frame = ttk.Frame(self, relief="flat", borderwidth=0, padding=5, style="Card.TFrame")

    def toggle(self):
        if self.show.get():
            self.sub_frame.pack(fill="x", expand=1, pady=(2,0))
            self.toggle_btn.configure(text='▼')
        else:
            self.sub_frame.forget()
            self.toggle_btn.configure(text='▶')