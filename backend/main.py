from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_400_BAD_REQUEST
import shutil
from pathlib import Path
from typing import List # typingモジュールからListをインポート
from addMusic import main as add_music_main
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
    print('uploadfile 内')

    # 保存先ディレクトリを指定
    save_directory = Path("images_dir")

    # ディレクトリが存在しない場合は作成
    save_directory.mkdir(parents=True, exist_ok=True)

    for image in images:
        print(image.filename)
        try:
            # 保存先の完全なパスを作成
            file_path = save_directory / f"temp_{image.filename}"
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="File not uploaded")

    add_music_main()
    return {"filename": [image.filename for image in images]}

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