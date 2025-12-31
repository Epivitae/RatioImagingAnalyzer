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
import os 

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

    # --- Show Logo Only (No Text) ---
    def show_logo(self, logo_path):
        self.fig.clear() 
        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        self.im_object = None
        self.cbar = None

        if logo_path and os.path.exists(logo_path):
            try:
                img_arr = plt.imread(logo_path)
                self.ax.imshow(img_arr, alpha=0.15) 
            except Exception:
                pass
        self.canvas.draw()

    def init_image(self, shape, cmap="jet"):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        self.im_object = self.ax.imshow(np.zeros(shape), cmap=cmap)
        self.cbar = self.fig.colorbar(self.im_object, ax=self.ax, shrink=0.6, pad=0.02, label='Ratio Value')
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
        self.plot_ax_right = None 
        self.plot_canvas = None
        
        self.btn_copy_all = None
        self.btn_copy_y = None
        
        self.is_calculating = False
        self.current_shape_mode = "rect" 
        self.ax_ref = None
        
        self.drag_cid = None
        self.last_drag_time = 0
        
        self.plot_mode = "ratio" 
        self.cached_x = None
        self.cached_series = None
        self.cached_unit = "s"
        self.cached_is_log = False
        self.cached_do_norm = False
        
        self.btn_mode_ratio = None
        self.btn_mode_num = None
        self.btn_mode_den = None
        self.btn_mode_combo = None 

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

    def _update_temp_roi_data(self, extents):
        xmin, xmax, ymin, ymax = extents
        if abs(xmax - xmin) < 1.0 or abs(ymax - ymin) < 1.0: return False
        
        if self.current_shape_mode == "rect":
            params = (xmin, ymin, xmax-xmin, ymax-ymin)
        elif self.current_shape_mode == "circle":
            w = xmax - xmin; h = ymax - ymin
            cx = xmin + w/2; cy = ymin + h/2
            params = ((cx, cy), w, h)
        else: return False

        mask = self._generate_mask(self.current_shape_mode, params)
        if mask is None: return False
        
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        
        self.temp_roi = {
            'type': self.current_shape_mode, 'params': params,
            'mask': mask, 'color': color, 'id_display': next_id
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
                self._trigger_plot()
        except Exception: pass

    def _on_select_finalize(self, eclick, erelease):
        try:
            if self._update_temp_roi_data(self.selector.extents):
                if self.app.live_plot_var.get(): self._trigger_plot()
        except Exception: pass

    def _on_poly_finalize(self, verts):
        mask = self._generate_mask("polygon", verts)
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        self.temp_roi = {'type': "polygon", 'params': verts, 'mask': mask, 'color': color, 'id_display': next_id}
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
            self.roi_list.append({'type': t['type'], 'patch': patch, 'mask': t['mask'], 'color': t['color'], 'id': len(self.roi_list) + 1})
            
        self.temp_roi = None
        self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get(): self._trigger_plot()

    def _trigger_plot(self):
        self.plot_curve(
            interval=self.app.var_interval.get(),
            unit=self.app.combo_unit.get(),
            is_log=self.app.log_var.get(),
            do_norm=self.app.norm_var.get(),
            int_thresh=self.app.var_int_thresh.get(),
            ratio_thresh=self.app.var_ratio_thresh.get()
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
        if self.app.live_plot_var.get(): self._trigger_plot()

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
            self.plot_ax.clear(); self.plot_canvas.draw()

    def plot_curve(self, interval=1.0, unit='s', is_log=False, do_norm=False, int_thresh=0, ratio_thresh=0):
        if not self.roi_list and not self.temp_roi: 
            if self.plot_ax: 
                self.plot_ax.clear()
                self.plot_canvas.draw()
            return
        if self.is_calculating: return

        data_num, data_den, bg_num, bg_den = self.app.get_active_data()
        if data_num is None: return
        self.is_calculating = True
        
        # [New] Get Aux Data
        data_aux_list = getattr(self.app, 'data_aux', [])
        bg_aux_list = getattr(self.app, 'cached_bg_aux', [])
        
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
            args=(data_num, data_den, bg_num, bg_den, data_aux_list, bg_aux_list, interval, unit, is_log, do_norm, task_list, int_thresh, ratio_thresh)
        ).start()

    def _calc_multi_roi_thread(self, data_num, data_den, bg_num, bg_den, data_aux_list, bg_aux_list, interval, unit, is_log, do_norm, task_list, int_thresh, ratio_thresh):
        try:
            results = []
            
            def calc_dff(arr):
                valid_mask = arr > 1e-6
                if not np.any(valid_mask): 
                    return np.zeros_like(arr)
                valid_vals = arr[valid_mask]
                thresh_5 = np.percentile(valid_vals, 5)
                baseline_vals = valid_vals[valid_vals <= thresh_5]
                f0 = np.mean(baseline_vals) if len(baseline_vals) > 0 else np.mean(valid_vals)
                if f0 > 1e-6:
                    return (arr - f0) / f0
                else:
                    return np.zeros_like(arr)

            for item in task_list:
                mask = item['mask']
                y_idxs, x_idxs = np.where(mask)
                
                if len(y_idxs) == 0:
                    means = np.zeros(data_num.shape[0])
                    results.append({'id': item['id'], 'color': item['color'], 'means': means, 'means_num': means, 'means_den': means, 'means_aux': []})
                    continue
                
                # --- Core Ratio Calculation ---
                roi_num = data_num[:, y_idxs, x_idxs].astype(np.float32) - bg_num
                roi_den = data_den[:, y_idxs, x_idxs].astype(np.float32) - bg_den
                
                roi_num = np.clip(roi_num, 0, None)
                roi_den = np.clip(roi_den, 0, None)
                
                mask_valid = (roi_num > int_thresh) & (roi_den > int_thresh) & (roi_den > 0.001)
                
                roi_ratio = np.full_like(roi_num, np.nan)
                np.divide(roi_num, roi_den, out=roi_ratio, where=mask_valid)
                if ratio_thresh > 0: roi_ratio[roi_ratio < ratio_thresh] = np.nan
                
                means_ratio = np.nanmean(roi_ratio, axis=1)
                means_ratio = np.nan_to_num(means_ratio, nan=0.0)
                
                means_num = np.nanmean(roi_num, axis=1)
                means_num = np.nan_to_num(means_num, nan=0.0)
                
                means_den = np.nanmean(roi_den, axis=1)
                means_den = np.nan_to_num(means_den, nan=0.0)
                
                # --- [New] Aux Calculation ---
                means_aux = []
                for i, d_aux in enumerate(data_aux_list):
                    bg_val = bg_aux_list[i] if i < len(bg_aux_list) else 0
                    # Slice ROI
                    roi_aux = d_aux[:, y_idxs, x_idxs].astype(np.float32) - bg_val
                    roi_aux = np.clip(roi_aux, 0, None)
                    m = np.nanmean(roi_aux, axis=1)
                    m = np.nan_to_num(m, nan=0.0)
                    if do_norm:
                        m = calc_dff(m)
                    means_aux.append(m)

                if do_norm:
                    means_ratio = calc_dff(means_ratio)
                    means_num = calc_dff(means_num)
                    means_den = calc_dff(means_den)
                
                results.append({
                    'id': item['id'],
                    'color': item['color'],
                    'means': means_ratio,
                    'means_num': means_num,
                    'means_den': means_den,
                    'means_aux': means_aux
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

    def _switch_plot_mode(self, mode):
        self.plot_mode = mode
        self._refresh_plot_canvas()

    def _show_window(self, x, series_list, unit, is_log, do_norm):
        self.cached_x = x
        self.cached_series = series_list
        self.cached_unit = unit
        self.cached_is_log = is_log
        self.cached_do_norm = do_norm

        if self.plot_window is None or not Toplevel.winfo_exists(self.plot_window):
            self.plot_window = Toplevel(self.app.root)
            self.plot_window.title(f"ROI Analysis")
            self.plot_window.geometry("750x550") 
            
            bf = ttk.Frame(self.plot_window, style="White.TFrame", padding=10)
            bf.pack(side="bottom", fill="x")
            
            bf_mode = ttk.Frame(bf, style="White.TFrame")
            bf_mode.pack(side="top", fill="x", pady=(0, 5))
            
            ttk.Label(bf_mode, text="View:", style="White.TLabel").pack(side="left")
            
            self.btn_mode_ratio = ttk.Button(bf_mode, text="Ratio", command=lambda: self._switch_plot_mode("ratio"), width=8)
            self.btn_mode_ratio.pack(side="left", padx=2)
            
            self.btn_mode_num = ttk.Button(bf_mode, text="Num", command=lambda: self._switch_plot_mode("num"), width=12)
            self.btn_mode_num.pack(side="left", padx=2)
            
            self.btn_mode_den = ttk.Button(bf_mode, text="Den", command=lambda: self._switch_plot_mode("den"), width=12)
            self.btn_mode_den.pack(side="left", padx=2)
            
            self.btn_mode_combo = ttk.Button(bf_mode, text="Combo (All)", command=lambda: self._switch_plot_mode("combo"), width=12)
            self.btn_mode_combo.pack(side="left", padx=(10, 2))

            bf_copy = ttk.Frame(bf, style="White.TFrame")
            bf_copy.pack(side="top", fill="x")
            
            self.btn_copy_all = ttk.Button(bf_copy, text="📋 Copy All Data")
            self.btn_copy_all.pack(side="left", padx=5)
            self.btn_copy_y = ttk.Button(bf_copy, text="🔢 Copy Y-Only")
            self.btn_copy_y.pack(side="left", padx=5)

            fig = plt.Figure(figsize=(5, 4), dpi=100)
            fig.patch.set_facecolor('#FFFFFF')
            self.plot_ax = fig.add_subplot(111)
            self.plot_canvas = FigureCanvasTkAgg(fig, master=self.plot_window)
            self.plot_canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=10, pady=10)

        try: mode_var = self.app.ratio_mode_var.get()
        except: mode_var = "c1_c2"
        
        txt_num = "Ch1 (Num)" if mode_var == "c1_c2" else "Ch2 (Num)"
        txt_den = "Ch2 (Den)" if mode_var == "c1_c2" else "Ch1 (Den)"
        
        if self.btn_mode_num: self.btn_mode_num.config(text=txt_num)
        if self.btn_mode_den: self.btn_mode_den.config(text=txt_den)
        
        try:
            style_active = "Success.TButton"
            style_normal = "TButton"
            self.btn_mode_ratio.config(style=style_active if self.plot_mode=="ratio" else style_normal)
            self.btn_mode_num.config(style=style_active if self.plot_mode=="num" else style_normal)
            self.btn_mode_den.config(style=style_active if self.plot_mode=="den" else style_normal)
            self.btn_mode_combo.config(style=style_active if self.plot_mode=="combo" else style_normal)
        except: pass

        self.btn_copy_all.configure(command=lambda: self._copy_multi_data(self.btn_copy_all, "📋 Copy All Data", x, series_list, mode="all"))
        self.btn_copy_y.configure(command=lambda: self._copy_multi_data(self.btn_copy_y, "🔢 Copy Y-Only", x, series_list, mode="y_only"))

        self._refresh_plot_canvas()

    def _refresh_plot_canvas(self):
        if not self.plot_ax: return
        
        if self.plot_ax_right is not None:
            self.plot_ax_right.remove()
            self.plot_ax_right = None
        
        x = self.cached_x
        series_list = self.cached_series
        unit = self.cached_unit
        is_log = self.cached_is_log
        do_norm = self.cached_do_norm
        
        self.plot_ax.clear()
        
        if self.plot_mode == "combo":
            use_dual_axis = not do_norm
            
            if use_dual_axis:
                self.plot_ax_right = self.plot_ax.twinx()
            
            lines = []
            
            for s in series_list:
                # Ratio
                l1, = self.plot_ax.plot(x, s['means'], color=s['color'], linestyle='-', linewidth=2, label=f"ROI {s['id']} Ratio")
                lines.append(l1)
                
                target_ax = self.plot_ax_right if use_dual_axis else self.plot_ax
                # Num / Den
                l2, = target_ax.plot(x, s['means_num'], color=s['color'], linestyle='--', linewidth=1, alpha=0.7, label=f"ROI {s['id']} Num")
                lines.append(l2)
                l3, = target_ax.plot(x, s['means_den'], color=s['color'], linestyle=':', linewidth=1, alpha=0.7, label=f"ROI {s['id']} Den")
                lines.append(l3)
                
                # [New] Aux Plotting
                if 'means_aux' in s:
                    for i, aux_data in enumerate(s['means_aux']):
                        # Use grey lines for Aux
                        l_aux, = target_ax.plot(x, aux_data, color='gray', linestyle='-.', linewidth=1, alpha=0.5, 
                                                label=f"ROI {s['id']} Aux{i+1}")
                        lines.append(l_aux)
            
            self.plot_ax.set_ylabel(r"$\Delta R / R_0$" if do_norm else "Ratio")
            if use_dual_axis:
                self.plot_ax_right.set_ylabel("Intensity (Raw)")
            
            self.plot_ax.set_xlabel(f"Time ({unit})")
            labels = [l.get_label() for l in lines]
            self.plot_ax.legend(lines, labels, loc='best', fontsize='small')
            
            self.plot_ax.grid(True, which="both", alpha=0.3)
            self.plot_canvas.figure.tight_layout()
            self.plot_canvas.draw()
            return

        # Single Modes
        data_key = 'means'
        if self.plot_mode == "num": data_key = 'means_num'
        elif self.plot_mode == "den": data_key = 'means_den'
        
        for s in series_list:
            y_data = s[data_key]
            self.plot_ax.plot(x, y_data, color=s['color'], label=f"ROI {s['id']}", linewidth=1.5)
            
        self.plot_ax.set_yscale('log' if (is_log and self.plot_mode=="ratio") else 'linear')
        
        try: mode_var = self.app.ratio_mode_var.get()
        except: mode_var = "c1_c2"

        if self.plot_mode == "ratio":
            if do_norm: ylabel = r"$\Delta R / R_0$"
            else: ylabel = "Ratio (Ch1/Ch2)" if mode_var == "c1_c2" else "Ratio (Ch2/Ch1)"
        elif self.plot_mode == "num":
            ch_name = "Ch1" if mode_var == "c1_c2" else "Ch2"
            if do_norm: ylabel = r"$\Delta F / F_0$ (" + ch_name + ")"
            else: ylabel = f"Intensity ({ch_name})"
        elif self.plot_mode == "den":
            ch_name = "Ch2" if mode_var == "c1_c2" else "Ch1"
            if do_norm: ylabel = r"$\Delta F / F_0$ (" + ch_name + ")"
            else: ylabel = f"Intensity ({ch_name})"
            
        self.plot_ax.set_ylabel(ylabel)
        self.plot_ax.set_xlabel(f"Time ({unit})")
        self.plot_ax.legend()
        self.plot_ax.grid(True, which="both", alpha=0.3)
        self.plot_canvas.figure.tight_layout()
        self.plot_canvas.draw()
        self.plot_window.lift()

    def _copy_multi_data(self, btn_widget, original_text, x, series_list, mode="all"):
        if self.plot_mode == "combo":
            header = "Time"
            for s in series_list:
                header += f"\tROI_{s['id']}_Ratio\tROI_{s['id']}_Num\tROI_{s['id']}_Den"
                if 'means_aux' in s:
                    for i in range(len(s['means_aux'])):
                        header += f"\tROI_{s['id']}_Aux{i+1}"
            header += "\n"
            
            content = ""
            for i in range(len(x)):
                row = f"{x[i]:.3f}"
                for s in series_list:
                    row += f"\t{s['means'][i]:.5f}\t{s['means_num'][i]:.5f}\t{s['means_den'][i]:.5f}"
                    if 'means_aux' in s:
                        for aux_val in s['means_aux']:
                            row += f"\t{aux_val[i]:.5f}"
                content += row + "\n"
        else:
            data_key = 'means'
            if self.plot_mode == "num": data_key = 'means_num'
            elif self.plot_mode == "den": data_key = 'means_den'

            if mode == "all":
                header = "Time" + "".join([f"\tROI_{s['id']}" for s in series_list]) + "\n"
            else:
                header = "\t".join([f"ROI_{s['id']}" for s in series_list]) + "\n"

            content = ""
            for i in range(len(x)):
                row = ""
                if mode == "all":
                    row += f"{x[i]:.3f}\t"
                vals = [f"{s[data_key][i]:.5f}" for s in series_list]
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