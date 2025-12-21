# Welcome to hunyaBOT

Powered by Avanzare Developer Team

## 主要な機能

Coming Soon...

## ファイル

| File | Description |
| ---- | ----------- |
| README.md | このファイル |
| Avanzare Mk2.py | メインの実行ファイル |
| requirements.txt | モジュールインストール用 |
| bot/config.py | Coming Soon... |
| bot/web.py | Flask実行ファイル（Web認証など） |

## ディレクトリ

| Dir | Description |
| --- | ----------- |
| bot/ | Bot用のファイル |
| bot/cogs/ | discord.pyのcogs（Botの機能） |

## 必要な環境

- Python 3.x.x (3.8, 3.9, 3.10, 3.11, 3.12)
- [venv](https://docs.python.org/ja/3/library/venv.html) (Python標準)
- git

## セットアップ

### 1. Cloneする

```text
https://github.com/AvanzareDeveloper-Team/hunyaBOT.git
```

### 2. venvで仮想環境を作る

他のプロジェクトと混ざらないように分けます

```sh
python3 -m venv venv
```

### 3. venv起動

```sh
# Windows
.\venv\Scripts\activate

# Linux/macOS
source ./venv/bin/activate
```

### 4. 必要なモジュールのインストール

```sh
pip3 install -r requirements.txt
```

### 5. Tokenなどを登録する

Coming Soon...

### 6. 実行

```sh
python3 "./Avanzare Mk2.py"
```

※ファイル名にスペースがあるので必ず `"` `"` でくくる

### 7. venvを終了する

```sh
deactivate
```

### VSCodeでvenvを使用する

VSCodeでPythonファイルを開いて、右下 ` 3.x.x ` をクリック

` Python 3.x.x (venv) ` ってやつを選択。（venvってついているやつ）

これをしてもまだ ` Import "discord" could not be resolved ` って出てたらPythonファイル開いた状態で ` Ctrl + P ` 押して

```text
>Python: Restart Language Server
```

を入力して実行。少ししたらなおる
