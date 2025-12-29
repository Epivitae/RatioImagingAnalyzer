# src/gui_components.py
import tkinter as tk
from tkinter import ttk, Toplevel, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector, EllipseSelector, PolygonSelector
from matplotlib.patches import Rectangle, Ellipse, Polygon
from matplotlib.path import Path as MplPath
from matplotlib.colors import LogNorm, Normalize
import threading
import time

ROI_COLORS = ['#FF3333', '#33FF33', '#3388FF', '#FFFF33', '#FF33FF', '#33FFFF', '#FF8833']

class PlotManager:
    def __init__(self, parent_frame):
        self.fig = plt.Figure(figsize=(6, 5), dpi=100)
        self.fig.patch.set_facecolor('#FFFFFF')
        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)
        
        self.im_object = None
        self.cbar = None
        self.toolbar = None

    def add_toolbar(self, parent_frame):
        self.toolbar = NavigationToolbar2Tk(self.canvas, parent_frame)
        self.toolbar.config(background="#FFFFFF")
        self.toolbar._message_label.config(background="#FFFFFF")
        self.toolbar.update()

    def init_image(self, shape, cmap="jet"):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        self.im_object = self.ax.imshow(np.zeros(shape), cmap=cmap)
        self.cbar = self.fig.colorbar(self.im_object, ax=self.ax, shrink=0.6, pad=0.02, label='Ratio (C1/C2)')
        self.canvas.draw()

    def update_image(self, img_data, vmin, vmax, log_scale=False, title=""):
        if self.im_object is None: return
        if log_scale:
            safe_vmin = max(vmin, 0.1)
            safe_vmax = max(vmax, safe_vmin * 1.1)
            norm = LogNorm(vmin=safe_vmin, vmax=safe_vmax)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax)
        self.im_object.set_data(img_data)
        self.im_object.set_norm(norm)
        if self.cbar: self.cbar.update_normal(self.im_object)
        self.ax.set_title(title)
        self.canvas.draw_idle()

    def update_cmap(self, cmap_name, bg_color_str):
        if self.im_object is None: return
        cmap = plt.get_cmap(cmap_name).copy()
        bg = bg_color_str.lower()
        if bg in ["transparent", "trans"]: cmap.set_bad(alpha=0)
        else: cmap.set_bad(bg)
        self.im_object.set_cmap(cmap)
        self.canvas.draw_idle()

    def resize(self, event):
        self.canvas.resize(event)
    
    def get_ax(self):
        return self.ax


class RoiManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.selector = None
        self.roi_list = [] 
        self.temp_roi = None
        
        self.plot_window = None
        self.plot_ax = None
        self.plot_canvas = None
        
        self.btn_copy_all = None
        self.btn_copy_y = None
        
        self.is_calculating = False
        self.current_shape_mode = "rect" 
        self.ax_ref = None
        
        self.drag_cid = None
        self.last_drag_time = 0

    def connect(self, ax):
        self.ax_ref = ax
        self.clear_all()

    def set_mode(self, mode):
        self.current_shape_mode = mode
        if self.temp_roi:
            self._commit_temp_roi()
        self._stop_selector()

    def start_drawing(self):
        if not self.ax_ref: return
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector()
        
        next_id = len(self.roi_list) + 1
        color_idx = (next_id - 1) % len(ROI_COLORS)
        color = ROI_COLORS[color_idx]
        
        props = dict(facecolor=color, edgecolor='black', alpha=0.2, linestyle='--', fill=True)
        line_props = dict(color='black', linestyle='--', linewidth=2, alpha=0.8)

        if self.current_shape_mode == "rect":
            self.selector = RectangleSelector(
                self.ax_ref, self._on_select_finalize, 
                useblit=True, button=[1], minspanx=5, minspany=5,
                spancoords='pixels', interactive=True, props=props
            )
        elif self.current_shape_mode == "circle":
            self.selector = EllipseSelector(
                self.ax_ref, self._on_select_finalize,
                useblit=True, button=[1], minspanx=5, minspany=5,
                spancoords='pixels', interactive=True, props=props
            )
        elif self.current_shape_mode == "polygon":
            self.selector = PolygonSelector(
                self.ax_ref, self._on_poly_finalize,
                useblit=True, props=line_props
            )

        if self.selector:
            self.selector.set_active(True)
            self.app.root.config(cursor="cross")
            
            if self.current_shape_mode in ["rect", "circle"]:
                self.drag_cid = self.app.plot_mgr.canvas.mpl_connect(
                    'motion_notify_event', self._on_drag_update
                )

    def _stop_selector(self):
        if self.drag_cid:
            self.app.plot_mgr.canvas.mpl_disconnect(self.drag_cid)
            self.drag_cid = None
            
        if self.selector:
            self.selector.set_active(False)
            self.selector.set_visible(False)
            self.selector = None
        self.app.root.config(cursor="")
        self.app.plot_mgr.canvas.draw_idle()

    # --- Core Logic to Update temp_roi ---
    def _update_temp_roi_data(self, extents):
        xmin, xmax, ymin, ymax = extents
        
        # [FIX] Ignore meaningless selections (clicks without drag)
        if abs(xmax - xmin) < 1.0 or abs(ymax - ymin) < 1.0:
            return False
        
        if self.current_shape_mode == "rect":
            params = (xmin, ymin, xmax-xmin, ymax-ymin)
        elif self.current_shape_mode == "circle":
            w = xmax - xmin
            h = ymax - ymin
            cx = xmin + w/2
            cy = ymin + h/2
            params = ((cx, cy), w, h)
        else:
            return False

        mask = self._generate_mask(self.current_shape_mode, params)
        if mask is None: return False
        
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        
        self.temp_roi = {
            'type': self.current_shape_mode,
            'params': params,
            'mask': mask,
            'color': color,
            'id_display': next_id
        }
        return True

    def _on_drag_update(self, event):
        if not self.selector or not self.selector.active: return
        if not event.inaxes: return
        if not self.app.live_plot_var.get(): return
        
        now = time.time()
        if now - self.last_drag_time < 0.1: return
        if self.is_calculating: return
        
        self.last_drag_time = now
        
        try:
            if self._update_temp_roi_data(self.selector.extents):
                self.plot_curve(
                    interval=self.app.var_interval.get(),
                    unit=self.app.combo_unit.get(),
                    is_log=self.app.log_var.get(),
                    do_norm=self.app.norm_var.get()
                )
        except Exception:
            pass

    def _on_select_finalize(self, eclick, erelease):
        try:
            # Always update data on release
            if self._update_temp_roi_data(self.selector.extents):
                # If Live is ON, plot immediately
                if self.app.live_plot_var.get():
                    self.plot_curve(
                        interval=self.app.var_interval.get(),
                        unit=self.app.combo_unit.get(),
                        is_log=self.app.log_var.get(),
                        do_norm=self.app.norm_var.get()
                    )
        except Exception:
            pass

    def _on_poly_finalize(self, verts):
        mask = self._generate_mask("polygon", verts)
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        
        self.temp_roi = {
            'type': "polygon",
            'params': verts,
            'mask': mask,
            'color': color,
            'id_display': next_id
        }
        self._commit_temp_roi()

    def _commit_temp_roi(self):
        if not self.temp_roi: return
        t = self.temp_roi
        patch = None
        
        if t['type'] == "rect":
            xmin, ymin, w, h = t['params']
            patch = Rectangle((xmin, ymin), w, h, linewidth=2, edgecolor='black', linestyle='--', facecolor=t['color'], alpha=0.3)
        elif t['type'] == "circle":
            center, w, h = t['params']
            patch = Ellipse(center, w, h, linewidth=2, edgecolor='black', linestyle='--', facecolor=t['color'], alpha=0.3)
        elif t['type'] == "polygon":
            patch = Polygon(t['params'], linewidth=2, edgecolor='black', linestyle='--', facecolor=t['color'], alpha=0.3, closed=True)
            
        if patch:
            self.ax_ref.add_patch(patch)
            self.roi_list.append({
                'type': t['type'],
                'patch': patch,
                'mask': t['mask'],
                'color': t['color'],
                'id': len(self.roi_list) + 1
            })
            
        self.temp_roi = None
        self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get():
            self.plot_curve(
                interval=self.app.var_interval.get(),
                unit=self.app.combo_unit.get(),
                is_log=self.app.log_var.get(),
                do_norm=self.app.norm_var.get()
            )

    def _generate_mask(self, shape_type, params):
        if self.app.data1 is None: return None
        h, w = self.app.data1.shape[1], self.app.data1.shape[2]
        
        if shape_type == "rect":
            xmin, ymin, width, height = params
            y, x = np.ogrid[:h, :w]
            return (x >= xmin) & (x <= xmin + width) & (y >= ymin) & (y <= ymin + height)
        elif shape_type == "circle":
            center, width, height = params
            y, x = np.ogrid[:h, :w]
            return (((x - center[0]) / (width/2))**2 + ((y - center[1]) / (height/2))**2) <= 1
        elif shape_type == "polygon":
            verts = params
            y, x = np.mgrid[:h, :w]
            points = np.vstack((x.ravel(), y.ravel())).T
            mpl_path = MplPath(verts)
            return mpl_path.contains_points(points).reshape(h, w)
        return None

    def remove_last(self):
        if self.temp_roi:
            self.temp_roi = None
            self._stop_selector()
        elif self.roi_list:
            item = self.roi_list.pop()
            try: item['patch'].remove()
            except: pass
            self.app.plot_mgr.canvas.draw_idle()
            
        if self.app.live_plot_var.get():
            self.plot_curve(
                interval=self.app.var_interval.get(),
                unit=self.app.combo_unit.get(),
                is_log=self.app.log_var.get(),
                do_norm=self.app.norm_var.get()
            )

    def clear_all(self):
        self._stop_selector()
        self.temp_roi = None
        for item in self.roi_list:
            try: item['patch'].remove()
            except: pass
        self.roi_list = []
        
        if self.ax_ref:
            for p in list(self.ax_ref.patches): p.remove()
            for l in list(self.ax_ref.lines): l.remove()
        
        if self.app.plot_mgr:
            self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get() and self.plot_ax:
            self.plot_ax.clear()
            self.plot_canvas.draw()

    def plot_curve(self, interval=1.0, unit='s', is_log=False, do_norm=False):
        if not self.roi_list and not self.temp_roi: 
            if self.plot_ax: 
                self.plot_ax.clear()
                self.plot_canvas.draw()
            return

        if self.is_calculating: return
        data1, data2 = self.app.data1, self.app.data2
        bg1, bg2 = self.app.cached_bg1, self.app.cached_bg2
        if data1 is None: return

        self.is_calculating = True
        
        task_list = []
        for r in self.roi_list:
            task_list.append({'mask': r['mask'], 'color': r['color'], 'id': r['id']})
        if self.temp_roi and self.temp_roi['mask'] is not None:
            task_list.append({'mask': self.temp_roi['mask'], 'color': self.temp_roi['color'], 'id': self.temp_roi['id_display']})

        if not task_list:
            self.is_calculating = False
            return

        threading.Thread(
            target=self._calc_multi_roi_thread, 
            args=(data1, data2, bg1, bg2, interval, unit, is_log, do_norm, task_list)
        ).start()

    def _calc_multi_roi_thread(self, data1, data2, bg1, bg2, interval, unit, is_log, do_norm, task_list):
        try:
            results = []
            d1_clean = np.clip(data1 - bg1, 0, None)
            d2_clean = np.clip(data2 - bg2, 0, None)
            
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio_stack = np.divide(d1_clean, d2_clean)
                ratio_stack[d2_clean == 0] = np.nan
            
            for item in task_list:
                mask = item['mask']
                y_idxs, x_idxs = np.where(mask)
                if len(y_idxs) == 0:
                    means = np.zeros(ratio_stack.shape[0])
                else:
                    roi_pixels = ratio_stack[:, y_idxs, x_idxs]
                    means = np.nanmean(roi_pixels, axis=1)
                
                if do_norm:
                    valid_means = means[~np.isnan(means)]
                    if len(valid_means) > 0:
                        thresh_5 = np.percentile(valid_means, 5)
                        r0 = np.mean(valid_means[valid_means <= thresh_5])
                        if r0 != 0:
                            means = (means - r0) / r0
                        else:
                            means = np.zeros_like(means)
                
                results.append({
                    'id': item['id'],
                    'color': item['color'],
                    'means': means
                })

            if not results: return

            mult = 1.0
            if unit == "m": mult = 1.0/60.0
            elif unit == "h": mult = 1.0/3600.0
            times = np.arange(len(results[0]['means'])) * interval * mult
            
            self.app.root.after(0, lambda: self._show_window(times, results, unit, is_log, do_norm))
        except Exception as e:
            print(f"Calc Error: {e}")
        finally:
            self.is_calculating = False

    def _show_window(self, x, series_list, unit, is_log, do_norm):
        if self.plot_window is None or not Toplevel.winfo_exists(self.plot_window):
            self.plot_window = Toplevel(self.app.root)
            self.plot_window.title(f"ROI Analysis")
            self.plot_window.geometry("700x500")
            
            bf = ttk.Frame(self.plot_window, style="White.TFrame", padding=10)
            bf.pack(side="bottom", fill="x")
            
            self.btn_copy_all = ttk.Button(bf, text="📋 Copy All Data")
            self.btn_copy_all.pack(side="left", padx=5)
            
            self.btn_copy_y = ttk.Button(bf, text="🔢 Copy Y-Only")
            self.btn_copy_y.pack(side="left", padx=5)

            fig = plt.Figure(figsize=(5, 4), dpi=100)
            fig.patch.set_facecolor('#FFFFFF')
            self.plot_ax = fig.add_subplot(111)
            self.plot_canvas = FigureCanvasTkAgg(fig, master=self.plot_window)
            self.plot_canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=10, pady=10)

        self.btn_copy_all.configure(command=lambda: self._copy_multi_data(self.btn_copy_all, "📋 Copy All Data", x, series_list, mode="all"))
        self.btn_copy_y.configure(command=lambda: self._copy_multi_data(self.btn_copy_y, "🔢 Copy Y-Only", x, series_list, mode="y_only"))

        self.plot_ax.clear()
        for s in series_list:
            self.plot_ax.plot(x, s['means'], color=s['color'], label=f"ROI {s['id']}", linewidth=1.5)
            
        self.plot_ax.set_yscale('log' if is_log else 'linear')
        
        if do_norm:
            self.plot_ax.set_ylabel(r"$\Delta R / R_0$")
        else:
            self.plot_ax.set_ylabel("Mean Ratio")
            
        self.plot_ax.set_xlabel(f"Time ({unit})")
        self.plot_ax.legend()
        self.plot_ax.grid(True, which="both", alpha=0.3)
        self.plot_canvas.figure.tight_layout()
        self.plot_canvas.draw()
        self.plot_window.lift()

    def _copy_multi_data(self, btn_widget, original_text, x, series_list, mode="all"):
        if mode == "all":
            header = "Time" + "".join([f"\tROI_{s['id']}" for s in series_list]) + "\n"
        else:
            header = "\t".join([f"ROI_{s['id']}" for s in series_list]) + "\n"

        content = ""
        for i in range(len(x)):
            row = ""
            if mode == "all":
                row += f"{x[i]:.3f}\t"
            vals = [f"{s['means'][i]:.5f}" for s in series_list]
            row += "\t".join(vals)
            content += row + "\n"
            
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(header + content)
        
        def restore():
            try:
                btn_widget.configure(text=original_text, state="normal")
            except: pass
            
        btn_widget.configure(text="✔ Copied!", state="disabled")
        self.app.root.after(1000, restore)