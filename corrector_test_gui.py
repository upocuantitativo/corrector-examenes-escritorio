"""
corrector_test_gui.py
=====================
Versión de ESCRITORIO (Tkinter) del corrector de exámenes TIPO TEST al que
ha convergido el proyecto. Es el gemelo del app móvil/PWA
(https://upocuantitativo.github.io/corrector-examenes/) y comparte el mismo
núcleo lógico (`test_corrector_core.py`): mismo prototipo de examen y la misma
forma de corregir (+0,30 acierto / −0,10 fallo; dudas y blancos no puntúan).

Uso:
    python corrector_test_gui.py
o doble clic en  CORRECTOR_TEST.bat

Flujo:
  1. Elige/crea un examen (arriba). Sus soluciones se guardan con un nombre.
  2. (Opcional) Define las soluciones a mano o desde un examen corregido.
  3. Carga la foto del examen del alumno.
  4. Calibra el examen una vez (clic en cada letra) y, en cada examen, marca 2
     referencias y pulsa «Detectar». O corrige a mano en el panel.
  5. Lee el resultado desglosado.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import numpy as np
from PIL import Image, ImageTk

import test_corrector_core as core

EXAMS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examenes_test.json")
OK_COL, BAD_COL, DUD_COL = "#1b9e44", "#d32f2f", "#f9a825"


class CorrectorTestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Corrector de Exámenes — Tipo Test")
        root.geometry("1180x760")

        self.lib = core.ExamLibrary.load(EXAMS_JSON)
        self.answers = {}                 # {q: 'a'|'b'|'c'|None|'doubt'}
        self.cur_page = 1
        self.pil_img = None               # PIL image actual
        self.tk_img = None
        self.gray = None                  # numpy gris para detección
        self.scale = 1.0                  # factor canvas/imagen
        self.anchors = []                 # [(x,y),(x,y)] en coords imagen
        self.mode = "idle"                # idle|calibrate|anchors
        self.cal_buf = []
        self.key_mode = False             # definir soluciones desde foto

        self._build_ui()
        self._refresh_exam_combo()
        self._load_exam(self.lib.cur)

    # ---------------- UI ----------------
    def _build_ui(self):
        left = ttk.Frame(self.root, padding=8); left.pack(side="left", fill="y")
        right = ttk.Frame(self.root, padding=8); right.pack(side="right", fill="both", expand=True)

        # --- Examen ---
        ttk.Label(left, text="1 · EXAMEN", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(left); row.pack(fill="x", pady=4)
        self.exam_combo = ttk.Combobox(row, state="readonly", width=30)
        self.exam_combo.pack(side="left", fill="x", expand=True)
        self.exam_combo.bind("<<ComboboxSelected>>", self._on_exam_selected)
        row2 = ttk.Frame(left); row2.pack(fill="x")
        ttk.Button(row2, text="➕ Nuevo", command=self._new_exam).pack(side="left")
        ttk.Button(row2, text="✏️ Renombrar", command=self._rename_exam).pack(side="left", padx=3)
        ttk.Button(row2, text="🗑️ Borrar", command=self._delete_exam).pack(side="left")

        # páginas
        pr = ttk.Frame(left); pr.pack(fill="x", pady=(6, 0))
        ttk.Label(pr, text="Páginas:").pack(side="left")
        self.page_mode_var = tk.IntVar(value=1)
        ttk.Radiobutton(pr, text="1", variable=self.page_mode_var, value=1,
                        command=self._on_page_mode).pack(side="left")
        ttk.Radiobutton(pr, text="2", variable=self.page_mode_var, value=2,
                        command=self._on_page_mode).pack(side="left")
        self.page_var = tk.IntVar(value=1)
        self.page_r1 = ttk.Radiobutton(pr, text="Pág.1 (1-4)", variable=self.page_var, value=1,
                                       command=self._on_cur_page)
        self.page_r2 = ttk.Radiobutton(pr, text="Pág.2 (5-10)", variable=self.page_var, value=2,
                                       command=self._on_cur_page)

        # --- Soluciones ---
        ttk.Label(left, text="SOLUCIONES CORRECTAS", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        ttk.Button(left, text="📷 Definir soluciones desde examen corregido",
                   command=self._key_from_photo).pack(fill="x")
        self.keys_frame = ttk.Frame(left); self.keys_frame.pack(fill="x", pady=4)

        # --- Captura / acciones ---
        ttk.Label(left, text="2 · EXAMEN DEL ALUMNO", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        ttk.Button(left, text="🖼️ Cargar foto…", command=self._load_image).pack(fill="x")
        ar = ttk.Frame(left); ar.pack(fill="x", pady=4)
        ttk.Button(ar, text="🎯 Calibrar", command=self._calibrate).pack(side="left")
        ttk.Button(ar, text="📍 Referencias", command=self._mark_anchors).pack(side="left", padx=3)
        ttk.Button(ar, text="✨ Detectar", command=self._detect_click).pack(side="left")
        sr = ttk.Frame(left); sr.pack(fill="x")
        ttk.Label(sr, text="Sensibilidad").pack(side="left")
        self.sens_var = tk.DoubleVar(value=1.6)
        ttk.Scale(sr, from_=1.1, to=2.6, variable=self.sens_var, command=lambda e: None).pack(
            side="left", fill="x", expand=True)
        ttk.Button(left, text="↺ Empezar examen nuevo", command=self._reset).pack(fill="x", pady=4)
        self.cal_status = ttk.Label(left, text="", wraplength=300, foreground="#555")
        self.cal_status.pack(anchor="w")

        # --- Resultados ---
        ttk.Label(left, text="3 · CORRECCIÓN", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.total_lbl = ttk.Label(left, text="", font=("Segoe UI", 12, "bold"))
        self.total_lbl.pack(anchor="w")
        self.detail_lbl = ttk.Label(left, text="", wraplength=300)
        self.detail_lbl.pack(anchor="w")
        self.results_frame = ttk.Frame(left); self.results_frame.pack(fill="x", pady=4)

        # --- Canvas ---
        self.hint = ttk.Label(right, text="Carga una foto del examen.", foreground="#0d47a1",
                              font=("Segoe UI", 10, "bold"))
        self.hint.pack(anchor="w")
        self.canvas = tk.Canvas(right, bg="#222", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

    # ---------------- Examen / soluciones ----------------
    def _refresh_exam_combo(self):
        self.exam_combo["values"] = self.lib.order
        if self.lib.cur:
            self.exam_combo.set(self.lib.cur)

    def _load_exam(self, name):
        self.lib.cur = name
        ex = self.lib.current()
        self.page_mode_var.set(ex.page_mode)
        self._on_page_mode(persist=False)
        self.answers = {}
        self.anchors = []; self.mode = "idle"; self.key_mode = False
        self._render_keys(); self._render_results(); self._refresh_cal_status()
        self.exam_combo.set(name)
        self._redraw()
        self.lib.save(EXAMS_JSON)

    def _on_exam_selected(self, _e):
        self._load_exam(self.exam_combo.get())

    def _new_exam(self):
        name = simpledialog.askstring("Nuevo examen", "Nombre del nuevo examen:", parent=self.root)
        if not name:
            return
        try:
            self.lib.add(name.strip())
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return
        self.lib.save(EXAMS_JSON); self._refresh_exam_combo(); self._load_exam(name.strip())

    def _rename_exam(self):
        ex = self.lib.current()
        name = simpledialog.askstring("Renombrar", "Nuevo nombre:", initialvalue=ex.name, parent=self.root)
        if not name:
            return
        try:
            self.lib.rename(ex.name, name.strip())
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return
        self.lib.save(EXAMS_JSON); self._refresh_exam_combo(); self._load_exam(name.strip())

    def _delete_exam(self):
        ex = self.lib.current()
        if not messagebox.askyesno("Borrar", f"¿Borrar «{ex.name}» con sus soluciones y calibración?"):
            return
        try:
            self.lib.delete(ex.name)
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return
        self.lib.save(EXAMS_JSON); self._refresh_exam_combo(); self._load_exam(self.lib.cur)

    def _render_keys(self):
        for w in self.keys_frame.winfo_children():
            w.destroy()
        ex = self.lib.current()
        for i in range(ex.nq):
            row = ttk.Frame(self.keys_frame); row.pack(fill="x")
            ttk.Label(row, text=f"{i+1:>2}", width=3).pack(side="left")
            for o in core.OPTS:
                sel = ex.keys[i] == o
                b = tk.Button(row, text=o, width=2,
                              bg=("#1565c0" if sel else "#eee"),
                              fg=("white" if sel else "black"),
                              command=lambda ii=i, oo=o: self._set_key(ii, oo))
                b.pack(side="left", padx=1)

    def _set_key(self, i, o):
        self.lib.current().keys[i] = o
        self.lib.save(EXAMS_JSON); self._render_keys(); self._render_results(); self._redraw()

    # ---------------- Páginas ----------------
    def _on_page_mode(self, persist=True):
        pm = self.page_mode_var.get()
        ex = self.lib.current()
        if persist:
            ex.page_mode = pm; self.lib.save(EXAMS_JSON)
        self.cur_page = 1; self.page_var.set(1)
        if pm == 2:
            self.page_r1.pack(side="left", padx=(8, 0)); self.page_r2.pack(side="left")
        else:
            self.page_r1.pack_forget(); self.page_r2.pack_forget()
        self.anchors = []; self.mode = "idle"
        self._refresh_cal_status(); self._redraw()

    def _on_cur_page(self):
        self.cur_page = self.page_var.get()
        self.anchors = []; self.mode = "idle"
        self._refresh_cal_status(); self._redraw()

    # ---------------- Imagen ----------------
    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Foto del examen",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp"), ("Todos", "*.*")])
        if not path:
            return
        self.pil_img = Image.open(path).convert("RGB")
        self.gray = core._to_gray(self.pil_img)
        self.anchors = []; self.mode = "idle"
        self._fit_and_show()

    def _fit_and_show(self):
        if self.pil_img is None:
            return
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 400)
        w, h = self.pil_img.size
        self.scale = min(cw / w, ch / h, 1.0)
        disp = self.pil_img.resize((max(1, int(w * self.scale)), max(1, int(h * self.scale))))
        self.tk_img = ImageTk.PhotoImage(disp)
        self._redraw()

    def _to_img(self, ev):
        return ev.x / self.scale, ev.y / self.scale

    def _on_canvas_click(self, ev):
        if self.pil_img is None:
            return
        p = self._to_img(ev)
        if self.mode == "calibrate":
            self._cal_tap(p)
        elif self.mode == "anchors":
            self._anchor_tap(p)

    # ---------------- Calibración ----------------
    def _page_questions(self):
        return self.lib.current().page_questions(self.cur_page)

    def _cal_count(self):
        return len(self._page_questions()) * 3

    def _calibrate(self):
        if self.pil_img is None:
            messagebox.showinfo("Calibrar", "Carga primero una foto del examen."); return
        self.mode = "calibrate"; self.cal_buf = []
        self._set_hint(self._cal_prompt()); self._redraw()

    def _cal_prompt(self):
        i, total = len(self.cal_buf), self._cal_count()
        if i >= total:
            return "Listo."
        qs = self._page_questions()
        q = qs[i // 3] + 1; o = core.OPTS[i % 3]
        tag = f" · pág.{self.cur_page}" if self.lib.current().page_mode == 2 else ""
        return f"Calibrando ({i+1}/{total}){tag}: clic en la letra «{o})» de la pregunta {q}"

    def _cal_tap(self, p):
        self.cal_buf.append(p)
        if len(self.cal_buf) >= self._cal_count():
            cal = core.points_from_taps(self.cal_buf)
            self.lib.current().calib[str(self.cur_page)] = cal
            self.lib.save(EXAMS_JSON)
            self.mode = "idle"; self._set_hint("✅ Calibrado.")
            self._refresh_cal_status()
        else:
            self._set_hint(self._cal_prompt())
        self._redraw()

    def _page_cal(self):
        return self.lib.current().calib.get(str(self.cur_page))

    def _refresh_cal_status(self):
        ex = self.lib.current(); m = ex.calib
        if ex.page_mode == 2:
            txt = (f"«{ex.name}»: pág.1 {'✅' if '1' in m else '⚠️ sin calibrar'} · "
                   f"pág.2 {'✅' if '2' in m else '⚠️ sin calibrar'}.")
        else:
            txt = (f"✅ «{ex.name}» calibrado." if "1" in m
                   else f"⚠️ «{ex.name}» sin calibrar (puedes corregir a mano).")
        self.cal_status.config(text=txt)

    # ---------------- Referencias ----------------
    def _mark_anchors(self):
        if not self._page_cal():
            messagebox.showinfo("Referencias", "Calibra primero este examen (página)."); return
        if self.pil_img is None:
            messagebox.showinfo("Referencias", "Carga una foto primero."); return
        qs = self._page_questions()
        self.mode = "anchors"; self.anchors = []
        self._set_hint(f"Referencia 1/2: clic en la «a)» de la pregunta {qs[0]+1}")
        self._redraw()

    def _anchor_tap(self, p):
        self.anchors.append(p)
        qs = self._page_questions()
        if len(self.anchors) >= 2:
            self.mode = "idle"; self._set_hint("Referencias listas."); self._detect()
        else:
            self._set_hint(f"Referencia 2/2: clic en la «c)» de la pregunta {qs[-1]+1}")
        self._redraw()

    # ---------------- Detección ----------------
    def _detect_click(self):
        if self.pil_img is None:
            messagebox.showinfo("Detectar", "Carga una foto primero."); return
        if not self._page_cal():
            messagebox.showinfo("Detectar", "Calibra este examen primero (apartado calibración)."); return
        if len(self.anchors) < 2:
            self._mark_anchors(); return
        self._detect()

    def _key_from_photo(self):
        if not self._page_cal():
            messagebox.showinfo("Definir soluciones",
                                "Calibra primero este examen; o define las soluciones a mano.")
            return
        self.key_mode = True
        messagebox.showinfo("Definir soluciones",
                            "Carga la foto del examen CORREGIDO, marca 2 referencias y «Detectar».\n"
                            "Lo detectado se guardará como SOLUCIONES (revísalas después).")

    def _detect(self):
        cal = self._page_cal()
        if not cal or self.gray is None:
            return
        pts = core.mapped_points(cal, self.anchors)
        qs = self._page_questions()
        res = core.detect_answers(self.gray, pts, qs, sens=float(self.sens_var.get()))
        ex = self.lib.current()
        if self.key_mode:
            for q, v in res.items():
                if v not in (None, core.DOUBT):
                    ex.keys[q] = v
            self.key_mode = False; self.lib.save(EXAMS_JSON)
            self._render_keys()
            self._set_hint("✅ Soluciones guardadas. Revísalas en el panel de soluciones.")
        else:
            self.answers.update(res)
        self._render_results(); self._redraw()

    # ---------------- Resultados ----------------
    def _answers_list(self):
        ex = self.lib.current()
        return [self.answers.get(i, None) for i in range(ex.nq)]

    def _render_results(self):
        for w in self.results_frame.winfo_children():
            w.destroy()
        ex = self.lib.current()
        r = core.grade(self._answers_list(), ex.keys)
        self.total_lbl.config(text=f"{r.puntos:.2f} / {r.max_puntos:.2f}  ·  Nota {r.nota10:.2f}/10")
        self.detail_lbl.config(
            text=f"{r.literal}  ·  Aciertos {r.aciertos} · Fallos {r.fallos} · "
                 f"Dudas {r.dudas} · En blanco {r.blancos}")
        icons = {"ok": ("✔", OK_COL), "mal": ("✘", BAD_COL), "duda": ("?", DUD_COL), "blanco": ("·", "#999")}
        for i in range(ex.nq):
            row = ttk.Frame(self.results_frame); row.pack(fill="x")
            ttk.Label(row, text=f"{i+1:>2}", width=3).pack(side="left")
            for o in core.OPTS:
                sel = self.answers.get(i) == o
                b = tk.Button(row, text=o, width=2,
                              bg=("#1565c0" if sel else "#eee"),
                              fg=("white" if sel else "black"),
                              command=lambda ii=i, oo=o: self._toggle_answer(ii, oo))
                b.pack(side="left", padx=1)
            ttk.Label(row, text=f"sol:{ex.keys[i]}", width=6).pack(side="left", padx=4)
            ch, col = icons[r.detalle[i]]
            tk.Label(row, text=ch, fg=col, font=("Segoe UI", 11, "bold")).pack(side="left")
            tk.Button(row, text="?", width=2, command=lambda ii=i: self._set_doubt(ii)).pack(side="left")

    def _toggle_answer(self, i, o):
        self.answers[i] = None if self.answers.get(i) == o else o
        self._render_results(); self._redraw()

    def _set_doubt(self, i):
        self.answers[i] = core.DOUBT
        self._render_results(); self._redraw()

    def _reset(self):
        self.answers = {}; self.anchors = []; self.mode = "idle"; self.key_mode = False
        self.cur_page = 1; self.page_var.set(1)
        self._render_results(); self._refresh_cal_status(); self._set_hint("Listo para un examen nuevo.")
        self._redraw()

    # ---------------- Dibujo ----------------
    def _set_hint(self, t):
        self.hint.config(text=t)

    def _redraw(self):
        self.canvas.delete("all")
        if self.tk_img is not None:
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        s = self.scale
        if self.mode == "calibrate":
            for (x, y) in self.cal_buf:
                self.canvas.create_oval(x*s-5, y*s-5, x*s+5, y*s+5, fill="#29b6f6", outline="white")
            return
        for (x, y) in self.anchors:
            self.canvas.create_oval(x*s-6, y*s-6, x*s+6, y*s+6, fill=DUD_COL, outline="white", width=2)
        cal = self._page_cal()
        if not cal or len(self.anchors) < 2:
            return
        pts = core.mapped_points(cal, self.anchors)
        ex = self.lib.current(); qs = self._page_questions()
        r = core.grade(self._answers_list(), ex.keys)
        for lq, q in enumerate(qs):
            cl = r.detalle[q]
            key = ex.keys[q]; stu = self.answers.get(q)
            kx, ky, rr = pts[lq*3 + core.OPTS.index(key)]
            if cl == "ok":
                self._ring(kx, ky, rr, OK_COL); self._glyph(kx, ky, rr, "✔", OK_COL)
            elif cl == "mal":
                self._ring(kx, ky, rr, OK_COL)
                if stu in core.OPTS:
                    sx, sy, _ = pts[lq*3 + core.OPTS.index(stu)]
                    self._ring(sx, sy, rr, BAD_COL); self._glyph(sx, sy, rr, "✘", BAD_COL)
            elif cl == "duda":
                ax, ay, _ = pts[lq*3]
                self._glyph(ax - rr*1.4, ay, rr, "?", DUD_COL)

    def _ring(self, x, y, r, col):
        s = self.scale; rr = r * 1.15 * s
        self.canvas.create_oval(x*s-rr, y*s-rr, x*s+rr, y*s+rr, outline=col, width=3)

    def _glyph(self, x, y, r, ch, col):
        s = self.scale; size = max(14, int(r * 1.3 * s))
        self.canvas.create_text((x + r*1.7)*s, y*s, text=ch, fill=col,
                                font=("Segoe UI", size, "bold"))


def main():
    root = tk.Tk()
    CorrectorTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
