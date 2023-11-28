import React from 'react';

export default function UploadPage() {

  const handleSubmit = async (event) => {
    event.preventDefault();

    const formData = new FormData();

    const files = event.target.images.files;
    for (let i = 0; i < files.length; i++) {
      formData.append('images', files[i]);
    }
    console.log(formData);

    const response = await fetch('http://localhost:8000/uploadfile/', {
      method: 'POST',
      body: formData,
    });

    console.log(response);

    // ここでサーバからのレスポンスを処理
  };

  return (
    <form onSubmit={handleSubmit}>
    <input type="file" name="images" multiple />

    <button type="submit">アップロード</button>
    </form>
  );
}