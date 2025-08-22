# Explore extraction results


``` python
import pandas as pd
from pathlib import Path
import os

# Get the base directory (parent of notebooks folder)
base_dir = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()

# Check if data/extracted directory exists
extracted_dir = base_dir / "data/extracted"
dfs = []
for f in os.listdir(extracted_dir):
    if f.endswith('.parquet'):
        df = pd.read_parquet(extracted_dir / f)
        dfs.append(df)
    
df_final = pd.concat(dfs, ignore_index=True)
df_final.to_parquet(base_dir / "data/extracted_sample_10.parquet", index=False)
```

``` python
df_success_time = (
    df_final
    .groupby('model_name')
    .agg(
        n = ('success', 'count'),
        success_rate = ('success', 'mean'),
        avg_extraction_time_seconds = ('extraction_time_seconds', 'mean')
    )
    .reset_index()
    .sort_values('success_rate', ascending=False)
)

df_success_time
```

<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }
&#10;    .dataframe tbody tr th {
        vertical-align: top;
    }
&#10;    .dataframe thead th {
        text-align: right;
    }
</style>

|     | model_name          | n   | success_rate | avg_extraction_time_seconds |
|-----|---------------------|-----|--------------|-----------------------------|
| 3   | Gemini 2.5 Pro      | 20  | 1.00         | 27.642346                   |
| 2   | Gemini 2.5 Flash    | 20  | 1.00         | 23.138534                   |
| 9   | OpenAI GPT-4.1-nano | 20  | 1.00         | 3.048855                    |
| 7   | OpenAI GPT-4.1      | 20  | 1.00         | 11.777276                   |
| 8   | OpenAI GPT-4.1-mini | 20  | 1.00         | 8.388023                    |
| 0   | GPT OSS 120B        | 20  | 0.95         | 4.027314                    |
| 1   | GPT OSS 20B         | 20  | 0.45         | 5.255857                    |
| 6   | Llama 4 Scout       | 20  | 0.20         | 3.076804                    |
| 5   | Llama 4 Maverick    | 20  | 0.10         | 2.181714                    |
| 4   | Kimi K2             | 20  | 0.05         | 10.743734                   |

</div>
