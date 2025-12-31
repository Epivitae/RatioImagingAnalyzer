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
import json # [New] Import json

try:
    from .plot_window import ROIPlotWindow
except ImportError:
    from plot_window import ROIPlotWindow

ROI_COLORS = ['#FF3333', '#33FF33', '#3388FF', '#FFFF33', '#FF33FF', '#33FFFF', '#FF8833']

# ... (PlotManager 类保持不变，此处省略) ...
class PlotManager:
    # ... (保持原样) ...
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
            except Exception: pass
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
        
        # 延迟导入以避免循环依赖
        try:
             from .plot_window import ROIPlotWindow
        except ImportError:
             from plot_window import ROIPlotWindow
        self.plot_window_controller = ROIPlotWindow(self.app.root)
        
        self.is_calculating = False
        self.current_shape_mode = "rect" 
        self.ax_ref = None
        
        self.drag_cid = None
        self.last_drag_time = 0
        
        self.btn_draw_ref = None

    def set_draw_button(self, btn_widget):
        self.btn_draw_ref = btn_widget

    def connect(self, ax):
        self.ax_ref = ax
        # 连接时不需要 complete_clear，只需清理数据结构
        self.roi_list = []
        self.temp_roi = None
        self._stop_selector()

    def set_mode(self, mode):
        self.current_shape_mode = mode
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector()

    def cancel_drawing(self):
        self._stop_selector()

    def start_drawing(self):
        if not self.ax_ref: return
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector() 
        
        if self.btn_draw_ref:
            self.btn_draw_ref.state(['selected']) 
            
        next_id = len(self.roi_list) + 1
        color_idx = (next_id - 1) % len(ROI_COLORS)
        color = ROI_COLORS[color_idx]
        
        # [修改 1] 交互绘制时的样式：提高不透明度(alpha 0.5)，加粗线条(linewidth 2)
        props = dict(facecolor=color, edgecolor='black', alpha=0.5, linestyle='--', linewidth=2, fill=True)
        line_props = dict(color='black', linestyle='--', linewidth=2, alpha=0.8)

        if self.current_shape_mode == "rect":
            self.selector = RectangleSelector(self.ax_ref, self._on_select_finalize, useblit=True, button=[1], minspanx=5, minspany=5, spancoords='pixels', interactive=True, props=props)
        elif self.current_shape_mode == "circle":
            self.selector = EllipseSelector(self.ax_ref, self._on_select_finalize, useblit=True, button=[1], minspanx=5, minspany=5, spancoords='pixels', interactive=True, props=props)
        elif self.current_shape_mode == "polygon":
            self.selector = PolygonSelector(self.ax_ref, self._on_poly_finalize, useblit=True, props=line_props)

        if self.selector:
            self.selector.set_active(True)
            self.app.root.config(cursor="cross")
            if self.current_shape_mode in ["rect", "circle"]:
                self.drag_cid = self.app.plot_mgr.canvas.mpl_connect('motion_notify_event', self._on_drag_update)

    def _stop_selector(self):
        if self.btn_draw_ref:
            self.btn_draw_ref.state(['!selected'])

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
        
        if self.current_shape_mode == "rect": params = (xmin, ymin, xmax-xmin, ymax-ymin)
        elif self.current_shape_mode == "circle":
            w = xmax - xmin; h = ymax - ymin; cx = xmin + w/2; cy = ymin + h/2
            params = ((cx, cy), w, h)
        else: return False

        mask = self._generate_mask(self.current_shape_mode, params)
        if mask is None: return False
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        self.temp_roi = {'type': self.current_shape_mode, 'params': params, 'mask': mask, 'color': color, 'id_display': next_id}
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
            if self._update_temp_roi_data(self.selector.extents): self._trigger_plot()
        except Exception as e: print(f"Drag error: {e}")

    def _on_select_finalize(self, eclick, erelease):
        try:
            if self._update_temp_roi_data(self.selector.extents):
                if self.app.live_plot_var.get(): self._trigger_plot()
        except Exception as e: print(f"Finalize error: {e}")

    def _on_poly_finalize(self, verts):
        mask = self._generate_mask("polygon", verts)
        if mask is None: return
        next_id = len(self.roi_list) + 1
        color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
        self.temp_roi = {'type': "polygon", 'params': verts, 'mask': mask, 'color': color, 'id_display': next_id}
        self._commit_temp_roi()

    # [修改 2] 核心修改：创建高对比度 ROI (填充层 + 白色实线层 + 黑色虚线层)
    def _create_high_contrast_roi(self, rtype, params, color):
        fill_alpha = 0.6 # 提高填充不透明度
        patches = []
        
        if rtype == "rect":
            x, y, w, h = params
            # 1. 填充层 (无边框)
            patches.append(Rectangle((x, y), w, h, linewidth=0, facecolor=color, alpha=fill_alpha))
            # 2. 白色底边框 (较粗实线)
            patches.append(Rectangle((x, y), w, h, linewidth=3, edgecolor='white', facecolor='none', linestyle='-'))
            # 3. 黑色顶边框 (较细虚线)
            patches.append(Rectangle((x, y), w, h, linewidth=2, edgecolor='black', facecolor='none', linestyle='--'))
            
        elif rtype == "circle":
            center, w, h = params
            # 1. 填充层
            patches.append(Ellipse(center, w, h, linewidth=0, facecolor=color, alpha=fill_alpha))
            # 2. 白色底边框
            patches.append(Ellipse(center, w, h, linewidth=3, edgecolor='white', facecolor='none', linestyle='-'))
            # 3. 黑色顶边框
            patches.append(Ellipse(center, w, h, linewidth=2, edgecolor='black', facecolor='none', linestyle='--'))
            
        elif rtype == "polygon":
            # 1. 填充层
            patches.append(Polygon(params, linewidth=0, facecolor=color, alpha=fill_alpha, closed=True))
            # 2. 白色底边框
            patches.append(Polygon(params, linewidth=3, edgecolor='white', facecolor='none', linestyle='-', closed=True))
            # 3. 黑色顶边框
            patches.append(Polygon(params, linewidth=2, edgecolor='black', facecolor='none', linestyle='--', closed=True))
            
        # 将所有 patch 添加到绘图区
        for p in patches:
            self.ax_ref.add_patch(p)
            
        return patches # 返回 patch 组

    def _commit_temp_roi(self):
        if not self.temp_roi: return
        t = self.temp_roi
        
        # 使用新方法创建高对比度 patch 组
        patch_group = self._create_high_contrast_roi(t['type'], t['params'], t['color'])
        
        if patch_group:
            # 存入列表的是 patch 组，而不是单个 patch
            self.roi_list.append({
                'type': t['type'], 
                'patch_group': patch_group, # [修改] 存储 patch 列表
                'mask': t['mask'], 
                'color': t['color'], 
                'id': len(self.roi_list) + 1,
                'params': t['params']
            })
        
        self.temp_roi = None
        self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get(): self._trigger_plot()

    def save_rois(self, filepath):
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector()

        if not self.roi_list:
            messagebox.showwarning("Save ROI", "No ROIs to save.")
            return
        
        data_to_save = []
        for roi in self.roi_list:
            item = {"type": roi['type'], "color": roi['color'], "id": roi['id']}
            if roi['type'] == "polygon": item["params"] = np.array(roi['params']).tolist() 
            else: item["params"] = roi['params']
            data_to_save.append(item)
            
        try:
            with open(filepath, 'w') as f: json.dump(data_to_save, f, indent=4)
            messagebox.showinfo("Success", f"Saved {len(data_to_save)} ROIs.")
        except Exception as e: messagebox.showerror("Error", f"Failed to save ROIs:\n{e}")

    def load_rois(self, filepath):
        if self.app.data1 is None:
            messagebox.showerror("Error", "Please load an image first.")
            return
        try:
            with open(filepath, 'r') as f: data_loaded = json.load(f)
            if not isinstance(data_loaded, list): raise ValueError("Invalid format.")

            self.clear_all() 
            
            for item in data_loaded:
                rtype = item["type"]
                params = item["params"]
                color = item.get("color", ROI_COLORS[0])
                
                if rtype == "polygon": params = np.array(params)
                else:
                    params = tuple(params)
                    if rtype == "circle": params = (tuple(params[0]), params[1], params[2])

                mask = self._generate_mask(rtype, params)
                if mask is None: continue
                
                # [修改 4] 加载时也使用高对比度样式
                patch_group = self._create_high_contrast_roi(rtype, params, color)
                
                if patch_group:
                    self.roi_list.append({
                        'type': rtype,
                        'patch_group': patch_group, # [修改]
                        'mask': mask,
                        'color': color,
                        'id': len(self.roi_list) + 1,
                        'params': params
                    })
            
            self.app.plot_mgr.canvas.draw_idle()
            messagebox.showinfo("Success", f"Loaded {len(self.roi_list)} ROIs.")
        except Exception as e: messagebox.showerror("Error", f"Failed to load ROIs:\n{e}")

    def _generate_mask(self, shape_type, params):
        if self.app.data1 is None: return None
        h, w = self.app.data1.shape[1], self.app.data1.shape[2]
        try:
            if shape_type == "rect":
                xmin, ymin, width, height = params
                y, x = np.ogrid[:h, :w]
                # 增加边界检查，防止浮点数误差导致 mask 全 false
                x_start, x_end = int(max(0, xmin)), int(min(w, xmin + width))
                y_start, y_end = int(max(0, ymin)), int(min(h, ymin + height))
                if x_start >= x_end or y_start >= y_end: return None
                mask = np.zeros((h, w), dtype=bool)
                mask[y_start:y_end, x_start:x_end] = True
                return mask
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
        except Exception as e:
             print(f"Mask generation error: {e}")
             return None
        return None

    def remove_last(self):
        if self.temp_roi:
            self.temp_roi = None
            self._stop_selector()
        elif self.roi_list:
            item = self.roi_list.pop()
            # [修改 3] 移除 patch 组中的所有 patch
            if 'patch_group' in item:
                for p in item['patch_group']:
                    try: p.remove()
                    except: pass
            self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get(): self._trigger_plot()

    def clear_all(self):
        self._stop_selector()
        self.temp_roi = None
        # [修改 3] 清理数据结构
        self.roi_list = []
        # 彻底清理 Ax 上的所有残留对象，确保干净
        if self.ax_ref:
            for p in list(self.ax_ref.patches): p.remove()
            for l in list(self.ax_ref.lines): l.remove()
        if self.app.plot_mgr: self.app.plot_mgr.canvas.draw_idle()

    def _trigger_plot(self):
        if not self.is_calculating: self.plot_curve()

    def plot_curve(self, interval=1.0, unit='s', is_log=False, do_norm=False, int_thresh=0, ratio_thresh=0):
        if not self.roi_list and not self.temp_roi: return
        if self.is_calculating: return

        data_num, data_den, bg_num, bg_den = self.app.get_active_data()
        if data_num is None: return
        
        # 简单的防抖
        self.is_calculating = True
        
        data_aux_list = getattr(self.app, 'data_aux', [])
        bg_aux_list = getattr(self.app, 'cached_bg_aux', [])
        
        task_list = []
        for r in self.roi_list:
            task_list.append({'mask': r['mask'], 'color': r['color'], 'id': r['id']})
        # 仅当 temp_roi 具有有效 mask 时才添加
        if self.temp_roi and self.temp_roi.get('mask') is not None:
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
                if not np.any(valid_mask): return np.zeros_like(arr)
                valid_vals = arr[valid_mask]
                thresh_5 = np.percentile(valid_vals, 5)
                baseline_vals = valid_vals[valid_vals <= thresh_5]
                f0 = np.mean(baseline_vals) if len(baseline_vals) > 0 else np.mean(valid_vals)
                if f0 > 1e-6: return (arr - f0) / f0
                else: return np.zeros_like(arr)

            for item in task_list:
                mask = item['mask']
                if mask is None or np.sum(mask) == 0:
                     means = np.zeros(data_num.shape[0])
                     results.append({'id': item['id'], 'color': item['color'], 'means': means, 'means_num': means, 'means_den': means, 'means_aux': []})
                     continue

                y_idxs, x_idxs = np.where(mask)
                
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
                
                means_aux = []
                for i, d_aux in enumerate(data_aux_list):
                    bg_val = bg_aux_list[i] if i < len(bg_aux_list) else 0
                    roi_aux = d_aux[:, y_idxs, x_idxs].astype(np.float32) - bg_val
                    roi_aux = np.clip(roi_aux, 0, None)
                    m = np.nanmean(roi_aux, axis=1)
                    m = np.nan_to_num(m, nan=0.0)
                    if do_norm: m = calc_dff(m)
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
            
            try: mode_var = self.app.ratio_mode_var.get()
            except: mode_var = "c1_c2"
            labels = ("Ch1", "Ch2") if mode_var == "c1_c2" else ("Ch2", "Ch1")

            self.app.root.after(0, lambda: self.plot_window_controller.update_data(
                times, results, unit, is_log, do_norm, labels
            ))
            
        except Exception as e:
            print(f"Calc Error: {e}")
        finally:
            self.is_calculating = False