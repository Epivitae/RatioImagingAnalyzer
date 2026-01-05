# src/constants.py

LANG_MAP = {
    "window_title": {"cn": "比率成像分析器 ({})", "en": "Ratio Imaging Analyzer ({})"},
    "header_title": {"cn": "Ratio Imaging Analyzer (RIA)", "en": "Ratio Imaging Analyzer (RIA)"},

    "grp_file": {"cn": "1. 文件加载", "en": "1. File Loading"},

    "grp_pre": {"cn": "2. 图像配准 (可选)", "en": "2. Image Registration (Optional)"},
    "btn_align": {"cn": "✨ 运行运动校正", "en": "✨ Run Motion Correction"},

    "btn_align_done": {"cn": "✔ 配准完成", "en": "✔ Reg. Complete"},
    "btn_undo_align": {"cn": "↩ 撤销", "en": "↩ Undo"},

    "btn_undo_done": {"cn": "✔ 已撤销", "en": "✔ Undone"},
    
    "lbl_align_info": {"cn": "基于 Ch1 校正位移 (需 OpenCV)", "en": "Aligns stack based on Ch1."},
    "msg_aligning": {"cn": "正在进行 ECC 配准...", "en": "Running ECC Alignment..."},

    
    "grp_calc": {"cn": "3. 参数校准", "en": "3. Calibration"},
    

    "grp_view": {"cn": "4. 显示设置", "en": "4. Display Settings"},


    "tab_sep": {"cn": " 分别导入 (两文件) ", "en": " Separate Files "},
    "tab_dual": {"cn": " 单文件多通道 ", "en": " Single File "},
    
    "btn_c1": {"cn": "📂 通道 1", "en": "📂 Ch1"},
    "btn_c2": {"cn": "📂 通道 2", "en": "📂 Ch2"},
    "btn_dual": {"cn": "📂 选择多通道文件", "en": "📂 Select File"},
    "chk_interleaved": {"cn": "交错堆栈", "en": "Mixed Stacks"},
    
    "btn_load": {"cn": "🚀 加载并分析", "en": "🚀 Load & Analyze"},
    "lbl_no_file": {"cn": "...", "en": "..."},
    
    "lbl_int_thr": {"cn": "强度阈值", "en": "Int. Min"},
    "lbl_ratio_thr": {"cn": "比率阈值", "en": "Ratio Min"},
    "lbl_smooth": {"cn": "平滑 (Smooth)", "en": "Smooth"},
    "lbl_bg": {"cn": "背景扣除 %", "en": "BG %"},
    "chk_log": {"cn": "📈 Log (对数显示)", "en": "📈 Log Scale"},

    "lbl_cmap": {"cn": "伪彩:", "en": "Colormap:"},
    "lbl_bg_col": {"cn": "背景色:", "en": "BG Color:"},
    "chk_lock": {"cn": "🔒 锁定范围", "en": "🔒 Lock Range"},
    "btn_apply": {"cn": "应用", "en": "Apply"},
    "lbl_roi_tools": {"cn": "🛠️ ROI & 测量", "en": "🛠️ ROI & Measurement"},
    "lbl_export": {"cn": "💾 数据导出", "en": "💾 Data Export"},
    "lbl_settings": {"cn": "⚙️ 其他设置", "en": "⚙️ Settings"},
    "btn_draw": {"cn": "✏️ 新建 (Ctrl+T)", "en": "✏️ New (Ctrl+T)"},
    "btn_clear": {"cn": "🗑️ 清除", "en": "🗑️ Clear"},
    "btn_plot": {"cn": "📈 生成曲线 (Ctrl+P)", "en": "📈 Plot Curve (Ctrl+P)"},
    "btn_save_stack": {"cn": "💾 保存序列 (Stack)", "en": "💾 Save Stack"},
    "btn_save_raw": {"cn": "💽 保存原始比值", "en": "💽 Save Raw Ratio"}, 
    "btn_save_frame": {"cn": "📷 保存当前帧", "en": "📷 Save Frame"}, 
    "btn_save_input": {"cn": "📥 保存预处理 Tiff", "en": "📥 Save Z-Proj Tiff"},
    "chk_live": {"cn": "🔴 实时监测 (Ctrl+L)", "en": "🔴 Live Monitor (Ctrl+L)"},
    "lbl_interval": {"cn": "Imaging Interval (s):", "en": "Imaging Interval (s):"}, 
    "lbl_unit": {"cn": "Plotting Unit:", "en": "Plotting Unit:"},
    "lbl_speed": {"cn": "倍速:", "en": "Speed:"},
    "btn_copy_all": {"cn": "📋 复制全部数据", "en": "📋 Copy All"},
    "btn_copy_y": {"cn": "🔢 仅复制 Ratio", "en": "🔢 Copy Ratio"},
    "btn_check_update": {"cn": "🔄 检查更新", "en": "🔄 Check Update"},
    "btn_contact": {"cn": "📧 联系作者", "en": "📧 Contact Author"},
    "msg_uptodate": {"cn": "当前已是最新版本！", "en": "You are up to date!"},
    "msg_new_ver": {"cn": "发现新版本: {}\n是否前往下载？", "en": "New version found: {}\nGo to download page?"},
    "title_update": {"cn": "版本更新", "en": "Update Check"},
    "err_check": {"cn": "检查更新失败: ", "en": "Check failed: "},
    "lbl_shape": {"cn": "ROI:", "en": "ROI:"},
    "lbl_ratio_mode": {"cn": "比率模式:", "en": "Ratio Mode:"},
    "mode_c1_c2": {"cn": "Ch1 / Ch2 (默认)", "en": "Ch1 / Ch2 (Default)"},
    "mode_c2_c1": {"cn": "Ch2 / Ch1 (反转)", "en": "Ch2 / Ch1 (Inverted)"},
}