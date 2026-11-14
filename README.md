# 鞋子文搜图

用英文搜索鞋子商品图。输入一次查询，页面并排显示 OpenCLIP 原始模型和鞋类微调模型各自的前 8 张结果。每张图附带相似度、鞋型、主色、主材质、颜色成分和材质成分。固定测试查询会显示每栏的 P@8、命中数和逐图命中状态。自由查询逐图显示未评分。

## 实验结果

两套模型在同一批 199 张测试图上排序，按同一份 qrels 对 21 条查询等权计算 P@8。总命中从 39/168 增至 89/168。14 条提升、6 条持平、1 条下降。提升按未舍入分数计算。

| 难度 | 查询数 | 原始模型 P@8 | 微调模型 P@8 | 提升（百分点） |
| --- | --- | --- | --- | --- |
| 易 | 7 | 44.64% | 67.86% | +23.21 |
| 中 | 8 | 17.19% | 51.56% | +34.38 |
| 难 | 6 | 6.25% | 37.50% | +31.25 |
| 总体 | 21 | 23.21% | 52.98% | +29.76 |

本次在 CPU 上用 956 张图训练 3 轮，批大小 8，学习率 1e-5，随机种子 42。更新文本编码器最后一个 Transformer 块和输出投影的 7,678,464 个参数。 三轮平均训练损失依次为 0.5007、0.2393 和 0.2198，首轮至末轮下降约 56.1%。

white shoes 从 0/8 提升到 7/8，white sneakers 从 0/8 提升到 6/8。两条黑白主次查询 q20、q21 均从 0/8 提升到 4/8。

材质主次仍有改进空间。q16（同时含皮革样材质和网布）从 2/8 提升到 5/8，q23（皮革样材质为主且含网布）仍为 0/8。knit shoes 从 2/8 降到 1/8。

<details>
<summary>21 条查询的逐条结果</summary>

| ID | 英文查询 | 原始模型 | 微调模型 |
| --- | --- | --- | --- |
| q01 | sneakers | 7/8（87.5%） | 7/8（87.5%） |
| q02 | sandals | 7/8（87.5%） | 8/8（100.0%） |
| q03 | flat shoes | 3/8（37.5%） | 3/8（37.5%） |
| q04 | high-heeled shoes | 1/8（12.5%） | 4/8（50.0%） |
| q05 | white shoes | 0/8（0.0%） | 7/8（87.5%） |
| q07 | leather-like shoes | 5/8（62.5%） | 8/8（100.0%） |
| q08 | knit shoes | 2/8（25.0%） | 1/8（12.5%） |
| q09 | white sneakers | 0/8（0.0%） | 6/8（75.0%） |
| q10 | black sandals | 2/8（25.0%） | 7/8（87.5%） |
| q11 | brown flat shoes | 4/8（50.0%） | 4/8（50.0%） |
| q12 | canvas flat shoes | 0/8（0.0%） | 1/8（12.5%） |
| q13 | mesh sneakers | 1/8（12.5%） | 1/8（12.5%） |
| q14 | leather-like sandals | 2/8（25.0%） | 4/8（50.0%） |
| q15 | black and white sneakers | 0/8（0.0%） | 5/8（62.5%） |
| q16 | sneakers with leather-like and mesh elements | 2/8（25.0%） | 5/8（62.5%） |
| q17 | white leather-like sneakers | 0/8（0.0%） | 3/8（37.5%） |
| q18 | brown leather-like flat shoes | 3/8（37.5%） | 3/8（37.5%） |
| q20 | white sneakers with black elements | 0/8（0.0%） | 4/8（50.0%） |
| q21 | black sneakers with white elements | 0/8（0.0%） | 4/8（50.0%） |
| q22 | white sneakers with gray elements | 0/8（0.0%） | 4/8（50.0%） |
| q23 | leather-like sneakers with mesh elements | 0/8（0.0%） | 0/8（0.0%） |

</details>

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `get_model_files.py` | 下载预训练权重及分词器 |
| `create_index.py` | 用冻结的视觉编码器生成测试图库向量 |
| `train.py` | 生成英文描述并微调文本编码器 |
| `shoe_retrieval.py` | 模型、图像预处理和数据加载 |
| `docker/app.py` | Flask 服务，使用 FAISS 为两套模型分别排序 |
| `frontend/` | 双栏检索页面 |
| `shoes_images/cleaned_dataset/` | 清洗后的数据集、词表和评估配置 |

## 本地运行

下面以 Windows PowerShell 和 Python 3.11 为例。进入仓库根目录后创建虚拟环境：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

1. **准备图片。** 将项目使用的鞋图按原文件名放入 `shoes_images/image1/` 至 `shoes_images/image6/`。路径对应 `cleaned_dataset/dataset.jsonl` 中的 `image_path`，以 `shoes_images/` 为根。原图通过项目数据包提供，默认不随代码提交。复现实验时请使用与标注对应的原图版本。
2. **下载模型并构建索引。**

   ```powershell
   .\.venv\Scripts\python.exe get_model_files.py
   .\.venv\Scripts\python.exe create_index.py --batch-size 8
   ```

   下载脚本从 Hugging Face 获取原始权重与分词器。建索引脚本生成 `model/shoe_gallery.npz`。已有相同权重和图库索引时可复用。

3. **训练微调模型。**

   ```powershell
   .\.venv\Scripts\python.exe -u train.py --epochs 3 --batch-size 8 --lr 1e-5 --seed 42
   ```

   完成后生成 `model/shoes_finetuned.pt`。仅体验原始模型时可跳过训练，右栏会提示尚未加载微调权重。CPU 可以运行，图片编码和训练耗时取决于设备。脚本在训练结束时写入检查点。

4. **启动页面。**

   ```powershell
   .\.venv\Scripts\python.exe docker/app.py
   ```

   打开 [本地检索页面](http://localhost:5000)，输入 `white sneakers with black elements`。训练完成后重新启动服务即可载入新权重。

### Docker

完成模型下载、图库索引和图片准备后，可以在项目根目录构建容器。微调权重存在时也会一并载入。

```powershell
docker build -t shoe-retrieval -f docker/Dockerfile .
docker run --rm -p 5000:5000 shoe-retrieval
```

## 数据与训练方法

清洗后的标注文件包含 1,199 条记录。956 张用于训练，199 张为测试图库，另有 44 条未分配记录。测试图库为原测试集和验证集的合并版本。

标签包含鞋型、主色、主材质、颜色成分和材质成分。训练程序生成英文描述，主属性写在鞋型前，额外成分写在 `with` 后。例如 `white leather-like sneakers with mesh elements`。`Leather` 表示皮革样外观。

微调冻结图像编码器，直接更新文本编码器最后一个 Transformer 块和输出投影。程序缓存冻结的图像向量，使用基于标注生成的多正样本配对和属性互换负样本计算 SigLIP 风格的成对损失。原始模型和微调模型共用同一份图像索引。

## P@8 怎么计算

`shoes_images/cleaned_dataset/retrieval_evaluation_merged/` 保存英文查询、结构化条件及 qrels。正式评估采用相关图数量至少为 8 的 21 条查询。每条查询的分数为前 8 张结果中符合全部条件的图片数除以 8。整体分数是 21 条查询的等权平均。

例如，`white sneakers with black elements` 要求鞋型为运动鞋、白色为主色且颜色成分含黑色。评分使用 `sample_id` 对照 qrels，相似度负责排名。自由查询仍可返回图片和标签，有对应 qrels 时才显示 P@8。评估配置记录标注文件的哈希，请保留 `dataset.jsonl` 的原始内容和换行格式。

## 来源与许可

项目原型来自 [bentrevett/clip-search](https://github.com/bentrevett/clip-search)，原许可见 [LICENSE](LICENSE)。模型来自 [timm/ViT-B-16-SigLIP-512](https://huggingface.co/timm/ViT-B-16-SigLIP-512)。代码许可与模型、数据集的使用许可分别遵循其来源条款。
