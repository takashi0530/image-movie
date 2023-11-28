from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_400_BAD_REQUEST
import shutil
from pathlib import Path
from typing import List # typingモジュールからListをインポート
from addMusic import main as add_music_main
import uuid  # 一時ディレクトリ名のためにUUIDを生成する

# test
from test import main as test_main
# デバッグ用
import pdb

app = FastAPI()

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # next.jsが実行されているオリジンのみを許可
    # allow_origins=["*"],  # next.jsが実行されているオリジンのみを許可
    allow_credentials=True,
    allow_methods=["*"],  # 任意のHTTPメソッドを許可
    allow_headers=["*"],  # 任意のHTTPヘッダーを許可
)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/uploadfile/")
async def upload_file(images: List[UploadFile] = Form(...)):
    # 一時ディレクトリの作成
    temp_dir = Path("target_images") / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 一時ディレクトリにファイルを保存
    for image in images:
        try:
            file_path = temp_dir / image.filename
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="File not uploaded")

    # 画像->動画 変換処理
    add_music_main(temp_dir)

    # 一時ディレクトリの削除
    shutil.rmtree(temp_dir)

    return {"message": "Files processed successfully"}

# test用
@app.post("/test/")
async def test():
    print('テスト 内')
    test_main()
    # add_music_main()
    return {"filename": ['テスト終了']}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)