# 关键 Bug 修复：5D 格式适配

**日期**: 2026-01-05
**状态**: ✅ 全部修复

---

## 问题根源

删除 Lazy Loading 后，数据格式统一为 5D：`(T, C, Z, Y, X)`

但很多处理函数仍然期望 3D 格式：`(T, Y, X)`

导致三个严重 bug：
1. **运动矫正崩溃** - `too many values to unpack (expected 3)`
2. **Plot Curve 无窗口** - 数组维度错误
3. **Kymograph 无图** - 同样的维度问题

---

## 修复详情

### 1. 运动矫正 (Image Registration)

**文件**: `src/ria_gui/model.py`
**函数**: `align_data()`, `apply_existing_alignment()`

**修复前**:
```python
d1_a, d2_a, mats = align_stack_ecc(self.data1, target, progress_callback)
# ❌ 直接传入 5D 数据，导致崩溃
```

**修复后**:
```python
# Convert to 3D for alignment
data1_3d = np.squeeze(self.data1)  # (T,C,Z,Y,X) → (T,Y,X)
data2_3d = np.squeeze(self.data2)

d1_a, d2_a, mats = align_stack_ecc(data1_3d, data2_3d, progress_callback)

# Restore to 5D
self.data1 = d1_a[:, np.newaxis, np.newaxis, :, :]
self.data2 = d2_a[:, np.newaxis, np.newaxis, :, :]
```

---

### 2. Plot Curve 绘图

**文件**: `src/ria_gui/gui_components.py`
**函数**: `_calc_multi_roi_thread()`

**修复前**:
```python
roi_num = data_num[:, y_idxs, x_idxs]
# ❌ 假设是 3D，但实际是 5D
```

**修复后**:
```python
# Squeeze to 3D first
data_num_3d = np.squeeze(data_num)
roi_num = data_num_3d[:, y_idxs, x_idxs]

# 同样处理 data_den 和 data_aux
data_den_3d = np.squeeze(data_den)
d_aux_3d = np.squeeze(d_aux)
```

---

### 3. Kymograph 绘图

**文件**: `src/ria_gui/gui.py`
**函数**: `update_kymograph_for_roi()`

**修复前**:
```python
kymo1 = extract_kymograph(d1 - bg1, p1, p2)
# ❌ d1 是 5D，但 extract_kymograph 需要 3D
```

**修复后**:
```python
# Convert to 3D
d1_3d = np.squeeze(d1)
if d2 is not None:
    d2_3d = np.squeeze(d2)

kymo1 = extract_kymograph(d1_3d - bg1, p1, p2)
```

---

## 通用策略

对于所有需要 3D 数据的处理函数：

1. **输入前**: 使用 `np.squeeze()` 移除单例维度 (C=1, Z=1)
2. **处理**: 在 3D 格式下执行算法
3. **输出后**: 如需存回 Model，使用 `[:, np.newaxis, np.newaxis, :, :]` 恢复 5D

**示例**:
```python
# Before processing
data_3d = np.squeeze(data_5d)  # (T,C,Z,Y,X) → (T,Y,X)

# Process
result = some_function(data_3d)

# After processing (if storing back)
result_5d = result[:, np.newaxis, np.newaxis, :, :]
```

---

## 测试清单

- [x] 运动矫正按钮正常工作
- [x] Plot Curve 正常显示窗口
- [x] Kymograph 正常显示图像
- [x] 所有功能与删除 Lazy Loading 前一致

---

## 相关文件

1. `src/ria_gui/model.py` - align_data, apply_existing_alignment
2. `src/ria_gui/gui_components.py` - _calc_multi_roi_thread
3. `src/ria_gui/gui.py` - update_kymograph_for_roi
4. `src/ria_gui/processing.py` - align_stack_ecc, extract_kymograph (unchanged)

---

## 后续优化建议

考虑在 `model.py` 中添加统一的 3D 转换接口：

```python
def to_3d(self, data):
    """Convert 5D data to 3D for processing"""
    return np.squeeze(data)

def to_5d(self, data_3d):
    """Restore 3D result to 5D format"""
    return data_3d[:, np.newaxis, np.newaxis, :, :]
```

这样可以避免重复代码，并且更容易维护。
