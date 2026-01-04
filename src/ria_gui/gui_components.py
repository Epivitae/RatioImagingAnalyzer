# src/gui_components.py
import tkinter as tk
from tkinter import ttk, Toplevel, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector, EllipseSelector, PolygonSelector
from matplotlib.patches import Rectangle, Ellipse, Polygon, Circle
from matplotlib.path import Path as MplPath
from matplotlib.colors import LogNorm, Normalize
import matplotlib.lines as mlines
import threading
import time
import os
import json

ROI_COLORS = ['#FF3333', '#33FF33', '#3388FF', '#FFFF33', '#FF33FF', '#33FFFF', '#FF8833']

class PlotManager:
    def __init__(self, parent_frame, app_instance):
        self.parent = parent_frame
        self.app = app_instance
        self.selector = None
        self.roi_list = [] 
        self.temp_roi = None
        
        try:
             from .plot_window import ROIPlotWindow
        except ImportError:
             try:
                 from plot_window import ROIPlotWindow
             except ImportError:
                 pass
        
        if 'ROIPlotWindow' in locals():
            self.plot_window_controller = ROIPlotWindow(self.app.root)
        else:
            self.plot_window_controller = None
        
        self.is_calculating = False
        self.current_shape_mode = "rect" 
        self.is_drawing_bg = False
        self.ax_ref = None
        self.btn_draw_ref = None

        self.fig = plt.Figure(figsize=(5, 5), dpi=100)
        self.fig.patch.set_facecolor('#FFFFFF')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        self.im_object = None
        self.cbar = None
        self.toolbar = None

    def add_toolbar(self, parent_frame):
        for child in parent_frame.winfo_children():
            child.destroy()
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

    def update_image(self, img_data, vmin, vmax, log_scale=False, title="", cbar_label=None):
        if self.im_object is None: return
        if log_scale:
            safe_vmin = max(vmin, 0.1)
            safe_vmax = max(vmax, safe_vmin * 1.1)
            norm = LogNorm(vmin=safe_vmin, vmax=safe_vmax)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax)
            
        self.im_object.set_data(img_data)
        self.im_object.set_norm(norm)
        if self.cbar: 
            self.cbar.update_normal(self.im_object)
            if cbar_label: self.cbar.set_label(cbar_label)
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
    
    def get_ax(self): return self.ax


class RoiManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.selector = None
        self.roi_list = [] 
        self.temp_roi = None
        
        # 直线交互状态
        self.line_start_pt = None
        self.temp_line_artist = None
        self.dragging_roi = None       
        self.dragging_point_idx = -1   # 0=起点, 1=终点, 2=中点(平移)
        
        # 事件连接 ID
        self.cid_press = None
        self.cid_release = None
        self.cid_motion = None
        
        self.is_calculating = False
        self.current_shape_mode = "rect" 
        self.ax_ref = None
        self.btn_draw_ref = None
        self.is_drawing_bg = False
        self.last_drag_time = 0

    def set_draw_button(self, btn_widget):
        self.btn_draw_ref = btn_widget

    def connect(self, ax):
        self.ax_ref = ax
        self.roi_list = []
        self.temp_roi = None
        self._stop_selector()

    # =========================================================
    #  逻辑控制
    # =========================================================

    def set_mode(self, mode):
        """切换 ROI 模式"""
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector(clear_events=True)
        self.current_shape_mode = mode

        if mode == "line":
            self._connect_line_events()
            self.app.root.config(cursor="cross")
        elif mode:
            self.app.root.config(cursor="cross")
        else:
            self.app.root.config(cursor="")

    def cancel_drawing(self):
        """ESC 键按下时调用"""
        self.line_start_pt = None
        if self.temp_line_artist:
            self.temp_line_artist.remove()
            self.temp_line_artist = None
            
        self._stop_selector(clear_events=True)
        self.current_shape_mode = None
        
        if self.btn_draw_ref: self.btn_draw_ref.state(['!selected'])
        self.app.root.config(cursor="")
        self.app.plot_mgr.canvas.draw_idle()

    def _connect_line_events(self):
        if self.app.plot_mgr and self.cid_press is None:
            canvas = self.app.plot_mgr.canvas
            self.cid_press = canvas.mpl_connect('button_press_event', self._on_line_press)
            self.cid_release = canvas.mpl_connect('button_release_event', self._on_line_release)
            self.cid_motion = canvas.mpl_connect('motion_notify_event', self._on_line_drag)

    def _stop_selector(self, clear_events=False):
        if self.btn_draw_ref: self.btn_draw_ref.state(['!selected'])

        if self.selector:
            self.selector.set_active(False)
            self.selector.set_visible(False)
            self.selector = None
        
        if clear_events:
            canvas = self.app.plot_mgr.canvas
            if self.cid_press:   canvas.mpl_disconnect(self.cid_press); self.cid_press = None
            if self.cid_release: canvas.mpl_disconnect(self.cid_release); self.cid_release = None
            if self.cid_motion:  canvas.mpl_disconnect(self.cid_motion); self.cid_motion = None

        self.app.plot_mgr.canvas.draw_idle()

    def start_drawing(self, mode=None, is_background=False):
        if not self.ax_ref: return
        
        target_mode = mode if mode else self.current_shape_mode
        self.set_mode(target_mode)
        
        self.is_drawing_bg = is_background 
        if self.btn_draw_ref: self.btn_draw_ref.state(['selected']) 
        
        if self.current_shape_mode == "line":
            return

        if self.is_drawing_bg:
            props = dict(facecolor='black', edgecolor='gray', alpha=0.3, linestyle=':', linewidth=1, fill=True)
            line_props = dict(color='gray', linestyle=':', linewidth=1, alpha=0.8)
        else:
            next_id = len(self.roi_list) + 1
            color_idx = (next_id - 1) % len(ROI_COLORS)
            color = ROI_COLORS[color_idx]
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

    # =========================================================
    #  直线交互逻辑 (支持平移与视觉增强)
    # =========================================================

    def _on_line_press(self, event):
        if event.inaxes != self.ax_ref: return
        if self.app.view_mode != "ratio" and self.app.view_mode != "ch1" and self.app.view_mode != "ch2" and not self.app.view_mode.startswith("aux"):
             return

        click_pt = (event.xdata, event.ydata)
        min_dist = float('inf')
        target_roi = None
        pt_idx = -1 
        
        threshold = 30.0 # 拾取阈值
        
        for roi in self.roi_list:
            if roi['type'] == 'line':
                p1, p2 = roi['params']
                
                # 计算端点距离
                d1 = np.hypot(p1[0]-click_pt[0], p1[1]-click_pt[1])
                d2 = np.hypot(p2[0]-click_pt[0], p2[1]-click_pt[1])
                
                # 计算中点距离 (平移手柄)
                mid_pt = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
                d_mid = np.hypot(mid_pt[0]-click_pt[0], mid_pt[1]-click_pt[1])
                
                # 优先检测端点，其次检测中点
                if d1 < threshold and d1 < min_dist:
                    min_dist = d1; target_roi = roi; pt_idx = 0
                if d2 < threshold and d2 < min_dist:
                    min_dist = d2; target_roi = roi; pt_idx = 1
                
                # 如果没点中端点，但点中了中间 (距离稍微放宽一点)
                if pt_idx == -1 and d_mid < threshold and d_mid < min_dist:
                    min_dist = d_mid; target_roi = roi; pt_idx = 2 # 2 代表中点
        
        if target_roi:
            self.dragging_roi = target_roi
            self.dragging_point_idx = pt_idx
            return 

        self.line_start_pt = (event.xdata, event.ydata)

    def _on_line_drag(self, event):
        if event.inaxes != self.ax_ref: return
        
        # A. 拖动模式
        if self.dragging_roi:
            p1, p2 = self.dragging_roi['params']
            new_pt = (event.xdata, event.ydata)
            
            # 0=起点, 1=终点, 2=平移
            if self.dragging_point_idx == 0:
                self.dragging_roi['params'] = (new_pt, p2)
            elif self.dragging_point_idx == 1:
                self.dragging_roi['params'] = (p1, new_pt)
            elif self.dragging_point_idx == 2:
                # 平移逻辑：计算中点位移量
                mid_old = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
                dx = new_pt[0] - mid_old[0]
                dy = new_pt[1] - mid_old[1]
                
                new_p1 = (p1[0] + dx, p1[1] + dy)
                new_p2 = (p2[0] + dx, p2[1] + dy)
                self.dragging_roi['params'] = (new_p1, new_p2)

            # 更新视觉 (Line + Circles)
            # patch_group 结构: [bg_line, fg_line, c_start, c_end, c_mid]
            group = self.dragging_roi['patch_group']
            bg_line, fg_line = group[0], group[1]
            c_start, c_end, c_mid = group[2], group[3], group[4] # 取出圆点
            
            curr_p1, curr_p2 = self.dragging_roi['params']
            curr_mid = ((curr_p1[0]+curr_p2[0])/2, (curr_p1[1]+curr_p2[1])/2)
            
            # 更新线
            bg_line.set_data([curr_p1[0], curr_p2[0]], [curr_p1[1], curr_p2[1]])
            fg_line.set_data([curr_p1[0], curr_p2[0]], [curr_p1[1], curr_p2[1]])
            
            # 更新圆点位置
            c_start.center = curr_p1
            c_end.center = curr_p2
            c_mid.center = curr_mid
            
            self.app.plot_mgr.canvas.draw_idle()
            
            if hasattr(self.app, 'update_kymograph_for_roi'):
                self.app.update_kymograph_for_roi(self.dragging_roi)
            return

        # B. 画新线预览
        if self.line_start_pt:
            x0, y0 = self.line_start_pt
            x1, y1 = event.xdata, event.ydata
            
            if self.temp_line_artist: self.temp_line_artist.remove()
            self.temp_line_artist = mlines.Line2D([x0, x1], [y0, y1], color='yellow', linestyle='--')
            self.ax_ref.add_line(self.temp_line_artist)
            self.app.plot_mgr.canvas.draw_idle()

    def _on_line_release(self, event):
        if self.dragging_roi:
            self.dragging_roi = None
            self.dragging_point_idx = -1
            return 

        if self.line_start_pt:
            if self.temp_line_artist:
                self.temp_line_artist.remove()
                self.temp_line_artist = None
            
            if event.xdata is not None and event.ydata is not None:
                end_pt = (event.xdata, event.ydata)
                dist = np.hypot(end_pt[0]-self.line_start_pt[0], end_pt[1]-self.line_start_pt[1])
                
                if dist > 5: 
                    params = (self.line_start_pt, end_pt)
                    next_id = len(self.roi_list) + 1
                    color = ROI_COLORS[(next_id - 1) % len(ROI_COLORS)]
                    patch_group = self._create_high_contrast_roi("line", params, color)

                    new_roi = {
                        'type': 'line', 
                        'patch_group': patch_group, 
                        'mask': None, 
                        'color': color, 
                        'id': next_id,
                        'params': params
                    }
                    self.roi_list.append(new_roi)
                    self.app.plot_mgr.canvas.draw_idle()
                    # 移除自动弹窗
            
            self.line_start_pt = None

    # =========================================================

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

    def _create_high_contrast_roi(self, rtype, params, color):
        patches = []
        if rtype == "line":
            (x1, y1), (x2, y2) = params
            mid_pt = ((x1+x2)/2, (y1+y2)/2)
            
            # 1. 线条
            line_bg = mlines.Line2D([x1, x2], [y1, y2], color='white', linewidth=3, alpha=0.8)
            line_fg = mlines.Line2D([x1, x2], [y1, y2], color=color, linewidth=1.5, linestyle='-')
            
            # 2. [新增] 端点圆圈 (起点, 终点)
            # 半径设为 4 (数据坐标系下的半径，如果图像很大可能需要调整，或者改用 Marker)
            # 这里使用 Circle patch，它会随着 zoom 缩放
            c_start = Circle((x1, y1), radius=4, color=color, alpha=0.6)
            c_end   = Circle((x2, y2), radius=4, color=color, alpha=0.6)
            
            # 3. [新增] 中点圆圈 (用于平移)
            c_mid   = Circle(mid_pt, radius=3, color='white', alpha=0.9, linewidth=1, edgecolor='black')

            self.ax_ref.add_line(line_bg)
            self.ax_ref.add_line(line_fg)
            self.ax_ref.add_patch(c_start)
            self.ax_ref.add_patch(c_end)
            self.ax_ref.add_patch(c_mid)
            
            # 返回顺序很重要，拖动更新时会用到
            return [line_bg, line_fg, c_start, c_end, c_mid]

        fill_alpha = 0.6
        if rtype == "rect":
            x, y, w, h = params
            patches.append(Rectangle((x, y), w, h, linewidth=0, facecolor=color, alpha=fill_alpha))
            patches.append(Rectangle((x, y), w, h, linewidth=3, edgecolor='white', facecolor='none', linestyle='-'))
            patches.append(Rectangle((x, y), w, h, linewidth=2, edgecolor='black', facecolor='none', linestyle='--'))
        elif rtype == "circle":
            center, w, h = params
            patches.append(Ellipse(center, w, h, linewidth=0, facecolor=color, alpha=fill_alpha))
            patches.append(Ellipse(center, w, h, linewidth=3, edgecolor='white', facecolor='none', linestyle='-'))
            patches.append(Ellipse(center, w, h, linewidth=2, edgecolor='black', facecolor='none', linestyle='--'))
        elif rtype == "polygon":
            patches.append(Polygon(params, linewidth=0, facecolor=color, alpha=fill_alpha, closed=True))
            patches.append(Polygon(params, linewidth=3, edgecolor='white', facecolor='none', linestyle='-', closed=True))
            patches.append(Polygon(params, linewidth=2, edgecolor='black', facecolor='none', linestyle='--', closed=True))
            
        for p in patches:
            self.ax_ref.add_patch(p)
        return patches

    def _commit_temp_roi(self):
        if not self.temp_roi: return
        t = self.temp_roi
        if self.is_drawing_bg:
            self._process_background_roi(t)
            self.temp_roi = None
            self._stop_selector()
            self.is_drawing_bg = False 
            self.app.root.config(cursor="")
            return

        patch_group = self._create_high_contrast_roi(t['type'], t['params'], t['color'])
        if patch_group:
            self.roi_list.append({
                'type': t['type'], 
                'patch_group': patch_group, 
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
                mask = None
                if rtype != "line":
                    mask = self._generate_mask(rtype, params)
                    if mask is None: continue
                patch_group = self._create_high_contrast_roi(rtype, params, color)
                if patch_group:
                    self.roi_list.append({
                        'type': rtype,
                        'patch_group': patch_group,
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
        except Exception: return None
        return None

    def remove_last(self):
        if self.current_shape_mode == "line" and self.line_start_pt:
            self.cancel_drawing()
            return
        if self.temp_roi:
            self.temp_roi = None
            self._stop_selector()
            return
        if self.roi_list:
            item = self.roi_list.pop()
            if 'patch_group' in item:
                for p in item['patch_group']:
                    try: p.remove()
                    except: pass
            self.app.plot_mgr.canvas.draw_idle()
        if self.app.live_plot_var.get(): self._trigger_plot()

    def clear_all(self):
        self.cancel_drawing() 
        self.temp_roi = None
        self.roi_list = []
        if self.ax_ref:
            for p in list(self.ax_ref.patches): p.remove()
            for l in list(self.ax_ref.lines): l.remove()
        if self.app.plot_mgr: self.app.plot_mgr.canvas.draw_idle()

    def _trigger_plot(self):
        if not self.is_calculating: self.plot_curve()

    def get_last_line_roi(self):
        for roi in reversed(self.roi_list):
            if roi['type'] == 'line':
                return roi
        return None

    def plot_curve(self, interval=1.0, unit='s', is_log=False, do_norm=False, int_thresh=0, ratio_thresh=0):
        if not self.roi_list and not self.temp_roi: return
        if self.is_calculating: return
        
        if not self.app.plot_mgr.plot_window_controller: return

        data_num, data_den, bg_num, bg_den = self.app.get_active_data()
        if data_num is None: return
        
        self.is_calculating = True
        
        data_aux_list = getattr(self.app, 'data_aux', [])
        bg_aux_list = getattr(self.app, 'cached_bg_aux', [])
        
        task_list = []
        for r in self.roi_list:
            task_list.append({'mask': r['mask'], 'color': r['color'], 'id': r['id']})
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
                if mask is None or np.sum(mask) == 0: continue

                y_idxs, x_idxs = np.where(mask)
                
                roi_num = data_num[:, y_idxs, x_idxs].astype(np.float32) - bg_num
                roi_num = np.clip(roi_num, 0, None)
                means_num = np.nanmean(roi_num, axis=1)
                means_num = np.nan_to_num(means_num, nan=0.0)

                if data_den is None:
                    means_ratio = means_num.copy()
                    means_den = np.zeros_like(means_num)
                else:
                    roi_den = data_den[:, y_idxs, x_idxs].astype(np.float32) - bg_den
                    roi_den = np.clip(roi_den, 0, None)
                    mask_valid = (roi_num > int_thresh) & (roi_den > int_thresh) & (roi_den > 0.001)
                    roi_ratio = np.full_like(roi_num, np.nan)
                    np.divide(roi_num, roi_den, out=roi_ratio, where=mask_valid)
                    if ratio_thresh > 0: roi_ratio[roi_ratio < ratio_thresh] = np.nan
                    means_ratio = np.nanmean(roi_ratio, axis=1)
                    means_ratio = np.nan_to_num(means_ratio, nan=0.0)
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
                    if data_den is not None: means_den = calc_dff(means_den)
                
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
            
            if data_den is None:
                labels = ("Intensity", "None")
                has_ratio = False
            else:
                labels = ("Ch1", "Ch2") if mode_var == "c1_c2" else ("Ch2", "Ch1")
                has_ratio = True
            
            aux_labels = []
            if data_aux_list:
                for i in range(len(data_aux_list)): aux_labels.append(f"Ch{i+3}")

            channel_info = {
                "labels": labels,
                "has_ratio": has_ratio,
                "aux_labels": aux_labels
            }

            self.app.root.after(0, lambda: self.app.plot_mgr.plot_window_controller.update_data(
                times, results, unit, is_log, do_norm, channel_info
            ))
            
        except Exception as e:
            print(f"Calc Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_calculating = False

    def _process_background_roi(self, roi_data):
        mask = roi_data['mask']
        if mask is None or self.app.data1 is None: return
        try:
            mean_img1 = np.mean(self.app.data1, axis=0) 
            bg_val1 = np.mean(mean_img1[mask])
            if self.app.data2 is not None:
                mean_img2 = np.mean(self.app.data2, axis=0)
                bg_val2 = np.mean(mean_img2[mask])
            else:
                bg_val2 = 0.0
            self.app.set_custom_background(float(bg_val1), float(bg_val2))
            if self.selector: self.selector.set_visible(False)
            self.app.plot_mgr.canvas.draw_idle()
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to calc background: {e}")

    # =========================================================
    #  [新增] 支持工程文件保存/加载的接口
    # =========================================================

    def get_all_rois_data(self):
        """
        获取当前所有 ROI 的纯数据列表（用于保存到 Project 文件）。
        """
        if self.temp_roi: self._commit_temp_roi()
        self._stop_selector()
        
        data_list = []
        for roi in self.roi_list:
            item = {"type": roi['type'], "color": roi['color'], "id": roi['id']}
            if roi['type'] == "polygon": 
                # numpy array 转 list 以便 JSON 序列化
                item["params"] = np.array(roi['params']).tolist() 
            else: 
                item["params"] = roi['params']
            data_list.append(item)
        return data_list

    def restore_rois_from_data(self, data_list):
        """
        从数据列表恢复 ROI（用于从 Project 文件加载）。
        """
        if self.app.data1 is None:
            # 如果没有加载图像，无法计算 Mask，因此无法恢复 ROI
            print("Warning: Cannot restore ROIs. No image data loaded.")
            return

        # 清除现有 ROI
        self.clear_all() 

        if not isinstance(data_list, list):
            return

        for item in data_list:
            try:
                rtype = item["type"]
                params = item["params"]
                color = item.get("color", ROI_COLORS[0])

                # 参数类型转换 (JSON 加载回来通常是 list，需要转回 tuple 或 numpy)
                if rtype == "polygon": 
                    params = np.array(params)
                else:
                    params = tuple(params)
                    # 特殊处理圆形的参数结构: ((x,y), w, h)
                    if rtype == "circle": 
                        params = (tuple(params[0]), params[1], params[2])

                # 生成 Mask
                mask = None
                if rtype != "line":
                    mask = self._generate_mask(rtype, params)
                    if mask is None: continue

                # 创建视觉元素
                patch_group = self._create_high_contrast_roi(rtype, params, color)
                
                if patch_group:
                    self.roi_list.append({
                        'type': rtype,
                        'patch_group': patch_group,
                        'mask': mask,
                        'color': color,
                        'id': len(self.roi_list) + 1,
                        'params': params
                    })
            except Exception as e: 
                print(f"Error restoring ROI: {e}")
        
        self.app.plot_mgr.canvas.draw_idle()