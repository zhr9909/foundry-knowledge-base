
# Minimal VRAM OCR Strategy

## 核心发现：不需要 detection 模型

我们一直以为 OCR 需要两步：
```
detection（找文字位置）→ recognition（认字）
    需要 ~800MB           需要 ~500MB
```

但注意——**table_rec 已经给了我们每个 cell 的精确位置！** 我们不需要 detection 模型再去"找"文字位置。

## 新方案：用 cell 边界做 OCR 区域

```
table_rec 输出：每个 cell 有 polygon（精确边界）
                    ↓
          直接用 cell 的 bbox 作为 OCR 区域
                    ↓
          recognition 模型直接认 cell 里的字
                    ↓
          DETECTION 模型完全不需要！省 ~800MB
```

## 只需加载的模型

| 模型 | 显存 | 说明 |
|------|------|------|
| table_rec | ~500MB | 识别表格行列结构 |
| recognition | ~500MB | OCR 认字 |
| **DETECTION** | **不需要** | ❌ 省了！ |
| **合计** | **~1GB** | ✅ |

对比之前：table_rec + detection + recognition = ~1.8GB，经常 CUDA 上下文竞争导致慢 15 倍。

## 模型生命周期

```
阶段1：加载 models（1次）
  table_rec → ~500MB
  recognition → ~500MB
  总计 ~1GB，6GB 显存有 5GB 空闲 ✅

阶段2：处理所有表格页（1979 页）
  table_rec 识别表结构
  recognition 读每个 cell 的字（用 cell bbox 直接切）
  模型不卸载，一直驻留

阶段3：卸载 models（1次）
  GPU 回到 0MB 占用

阶段4：处理纯文本页（1491 页）
  PyMuPDF 纯 CPU，不占显存
  速度 ~1s/页
```

## 预估速度

| 环节 | 页数 | 单页耗时 | 总计 |
|------|------|---------|------|
| table_rec + OCR | 1979 | ~15s | ~8.3h |
| 纯文本（PyMuPDF） | 1491 | ~1s | ~0.4h |
| **合计** | **3470** | - | **~9h** |

## 关键技术验证点

recognition 模型直接读 cell crop（不是 text line crop），需要验证：
- 单数字 cell："39" → 应正常 ✅（已验证）
- 文本 cell："Extruded pipe and tube(b)" → 应正常 ✅（已验证）
- 分隔点 cell：". . ." → 可能返回乱码，但可以过滤掉

## vs 其他方案

| 方案 | 显存 | 速度 | 完整性 |
|------|------|------|--------|
| 旧管线（PyMuPDF only） | 0.5GB | 3.5h | 表格缺数据 |
| **新方案（无 detection）** | **~1GB** | **~9h** | **表格完整** |
| 完整 OCR（含 detection） | ~1.8GB | ~20h+ | 表格完整（但慢） |
| Marker 全管线 | ~4.5GB | ~19h | 表格完整 |
