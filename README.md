# 鞋子文搜图

用英文搜索鞋子商品图。输入一次查询，页面显示四路各自的前 8 张结果：原始 SigLIP、文本侧微调 SigLIP、原始 SigLIP + 逻辑回归重排、原始 SigLIP + 线性 SVM 重排。每张图附带排序分数和五项标签。固定测试查询显示每栏的 P@8、命中数和逐图命中状态。自由查询逐图显示未评分。

## 实验结果

四组在同一批 199 张测试图上排序，使用同一份 qrels 对 21 条固定查询等权计算 P@8。

| 难度 | 查询数 | 原始 SigLIP | 文本侧微调 | 逻辑回归重排 | 线性 SVM 重排 |
| --- | --- | --- | --- | --- | --- |
| 易 | 7 | 73.21% | 82.14% | 87.50% | 89.29% |
| 中 | 8 | 59.38% | 71.88% | 64.06% | 68.75% |
| 难 | 6 | 39.58% | 50.00% | 41.67% | 50.00% |
| 总体 | 21 | 58.33% | 69.05% | 65.48% | 70.24% |

四组分别命中 98/168、116/168、110/168 和 118/168。相对原始 SigLIP，文本微调、逻辑回归和线性 SVM 分别提升 10.71、7.14、11.90 个百分点。差值按未舍入分数计算。

文本侧微调使用 956 张图训练 3 轮，批大小 8，学习率 1e-5，种子 42。三轮平均损失为 0.2288、0.1375、0.1155。

| 方法 | 鞋型 C | 主色 C | 鞋型权重 | 主色权重 | 验证 P@8 |
| --- | --- | --- | --- | --- | --- |
| 逻辑回归重排 | 10.0 | 10.0 | 0.25 | 0.00 | 66.67% |
| 线性 SVM 重排 | 10.0 | 1.0 | 0.10 | 0.00 | 63.69% |

两路都训练了鞋型和主色分类头。内部验证选出的主色融合系数均为 0，因此本次重排只融合鞋型分数。

线性 SVM 以 70.24% 居首，文本侧微调为 69.05%，逻辑回归为 65.48%。SVM 比微调合计多命中 2 张，相差 1.19 个百分点，难组两者同为 50.00%。这组结果支持在项目中保留两种路线，差距仍需在更大且独立的查询集上复核。

mesh sneakers 四组依次为 1/8、4/8、3/8、2/8。q16 同时要求皮革样材质和网布，SVM 为 6/8，微调为 4/8。q23 进一步要求皮革样材质为主，两路重排均为 0/8，基线和微调均为 1/8。鞋型加分可能把材质条件更符合的图片挤出前 8。

<details>
<summary>21 条固定查询的逐条命中数</summary>

每格为前 8 张中的命中数，除以 8 即为该条 P@8。

| ID | 英文查询 | 原始 | 微调 | 逻辑回归 | 线性 SVM |
| --- | --- | --- | --- | --- | --- |
| q01 | `sneakers` | 4/8 | 8/8 | 8/8 | 8/8 |
| q02 | `sandals` | 8/8 | 8/8 | 8/8 | 8/8 |
| q03 | `flat shoes` | 5/8 | 6/8 | 8/8 | 8/8 |
| q04 | `high-heeled shoes` | 6/8 | 6/8 | 7/8 | 8/8 |
| q05 | `white shoes` | 8/8 | 8/8 | 8/8 | 8/8 |
| q07 | `leather-like shoes` | 8/8 | 8/8 | 8/8 | 8/8 |
| q08 | `knit shoes` | 2/8 | 2/8 | 2/8 | 2/8 |
| q09 | `white sneakers` | 5/8 | 7/8 | 6/8 | 7/8 |
| q10 | `black sandals` | 6/8 | 6/8 | 7/8 | 7/8 |
| q11 | `brown flat shoes` | 5/8 | 5/8 | 2/8 | 5/8 |
| q12 | `canvas flat shoes` | 7/8 | 7/8 | 6/8 | 5/8 |
| q13 | `mesh sneakers` | 1/8 | 4/8 | 3/8 | 2/8 |
| q14 | `leather-like sandals` | 7/8 | 8/8 | 6/8 | 7/8 |
| q15 | `black and white sneakers` | 4/8 | 5/8 | 7/8 | 5/8 |
| q16 | `sneakers with leather-like and mesh elements` | 3/8 | 4/8 | 4/8 | 6/8 |
| q17 | `white leather-like sneakers` | 3/8 | 6/8 | 6/8 | 6/8 |
| q18 | `brown leather-like flat shoes` | 5/8 | 4/8 | 3/8 | 4/8 |
| q20 | `white sneakers with black elements` | 4/8 | 3/8 | 4/8 | 4/8 |
| q21 | `black sneakers with white elements` | 2/8 | 5/8 | 3/8 | 5/8 |
| q22 | `white sneakers with gray elements` | 4/8 | 5/8 | 4/8 | 5/8 |
| q23 | `leather-like sneakers with mesh elements` | 1/8 | 1/8 | 0/8 | 0/8 |

</details>

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `get_model_files.py` | 下载预训练权重及分词器 |
| `create_index.py` | 用冻结的视觉编码器生成测试图库向量 |
| `train.py` | 生成英文描述并微调文本编码器 |
| `train_rerankers.py` | 训练逻辑回归和线性 SVM，生成按测试图片 ID 对齐的预测表 |
| `shoe_retrieval.py` | 模型、图像预处理和数据加载 |
| `docker/app.py` | Flask 服务，计算四路检索结果与 P@8 |
| `frontend/` | 全英文四栏检索页面 |
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

   完成后生成 `model/shoes_finetuned.pt`。可跳过这一步，微调栏会提示尚未加载微调权重。CPU 可以运行，图片编码和训练耗时取决于设备。脚本在训练结束时写入检查点。

4. **训练两组属性重排。**

   ```powershell
   .\.venv\Scripts\python.exe -u train_rerankers.py
   ```

   生成 `model/logistic_regression.npz` 和 `model/linear_svm.npz`。首次训练会提取 956 张训练图的特征。更新图库、原始权重或预处理后，先重建图库，再重新运行本步骤。

5. **启动页面。**

   ```powershell
   .\.venv\Scripts\python.exe docker/app.py
   ```

   打开 [本地检索页面](http://localhost:5000)，输入 `white sneakers with black elements`。如果已有可用的原始权重、索引和正式微调权重，更新依赖后可直接从第 4 步开始。训练完成后重新启动服务以载入新文件。

### Docker

完成模型下载、图库索引和图片准备后，可以在项目根目录构建容器。如果已生成微调权重和属性预测表，构建时会一并复制到镜像中。

```powershell
docker build -t shoe-retrieval -f docker/Dockerfile .
docker run --rm -p 5000:5000 shoe-retrieval
```

## 数据与训练方法

清洗后的标注文件包含 1,199 条记录。956 张用于训练，199 张为测试图库，另有 44 条未分配记录。测试图库为原测试集和验证集的合并版本。

标签包含鞋型、主色、主材质、颜色成分和材质成分。训练程序生成英文描述，主属性写在鞋型前，额外成分写在 `with` 后。例如 `white leather-like sneakers with mesh elements`。`Leather` 表示皮革样外观。

微调冻结图像编码器，直接更新文本编码器最后一个 Transformer 块和输出投影。程序缓存冻结的图像向量，使用基于标注生成的多正样本配对和属性互换负样本计算 SigLIP 风格的成对损失。原始模型和微调模型共用同一份图像索引。

训练和建索引统一读取模型发布配置。图片经双三次插值直接缩放至 512 × 512，RGB 各通道均值和标准差均为 0.5。图库和微调检查点保存预处理指纹。

升级旧版本后，请重新运行 `create_index.py` 和 `train.py`，再重启服务。

## P@8 怎么计算

两组属性重排共用冻结的 SigLIP 图像特征，从原训练集按主色分层划出 765 张拟合图和 191 张内部验证图，种子为 42。原数据划分不变。由于没有商品分组 ID，内部验证按图片划分。每个分类头按验证 Macro-F1 选择 C，鞋型和主色融合系数按验证 P@8 选择。选定后用完整训练集重拟合，对测试图库生成概率表。两表保存分组 ID、系数和图库指纹，服务启动时校验并加载。

固定查询只用预设的鞋型和主色给全部候选图加分。无适用属性或系数为零时，重排栏沿用原始排序并提示未启用。

`shoes_images/cleaned_dataset/retrieval_evaluation_merged/` 保存英文查询、结构化条件及 qrels。正式评估采用相关图数量至少为 8 的 21 条查询。每条查询的分数为前 8 张结果中符合全部条件的图片数除以 8。整体分数是 21 条查询的等权平均。

例如，`white sneakers with black elements` 要求鞋型为运动鞋、白色为主色且颜色成分含黑色。评分使用 `sample_id` 对照 qrels，相似度负责排名。自由查询仍可返回图片和标签，有对应 qrels 时才显示 P@8。评估配置记录标注文件的哈希，请保留 `dataset.jsonl` 的原始内容和换行格式。

## 来源与许可

项目原型来自 [bentrevett/clip-search](https://github.com/bentrevett/clip-search)，原许可见 [LICENSE](LICENSE)。模型来自 [timm/ViT-B-16-SigLIP-512](https://huggingface.co/timm/ViT-B-16-SigLIP-512)。代码许可与模型、数据集的使用许可分别遵循其来源条款。
