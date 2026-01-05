# 1. Imagem base
FROM python:3.9-slim

# 2. Define pasta de trabalho
WORKDIR /app

# 3. Copia os arquivos
COPY . /app

# 4. Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# 5. Expõe a porta do Render
EXPOSE 10000

# 6. O comando para iniciar (O tal Docker Command)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
