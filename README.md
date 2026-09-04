# Mesclador Universal

Aplicativo web em Python para **mesclar, juntar e concatenar** arquivos, preservando o formato e o conteúdo original sempre que for tecnicamente possível.

Endereço padrão:

[http://localhost:5111](http://localhost:5111)

Este projeto **não é um conversor genérico**. Conversão ou transcodificação só ocorre internamente quando for necessária para conseguir unir os arquivos (por exemplo, dois MP4 com codecs diferentes).

## O que o aplicativo faz

1. Você seleciona dois ou mais arquivos.
2. Organiza a ordem (arrastar, subir, descer ou remover).
3. O sistema identifica o tipo e o formato.
4. Valida compatibilidade.
5. Mescla com o processador do formato.
6. Disponibiliza o resultado para download.

## Formatos suportados

| Tipo | Formatos | Resultado |
| --- | --- | --- |
| Áudio | AAC, FLAC, M4A, MP3, OGG, WAV, WMA | mesmo formato do primeiro arquivo |
| Vídeo | AVI, MKV, MOV, MP4, WEBM | mesmo container do primeiro arquivo, em geral |
| Imagens | BMP, JPEG, JPG, PNG, TIF, TIFF, WEBP | PDF |
| Documento | PDF, DOC, DOCX, TXT | PDF, DOCX ou TXT |
| Planilha | CSV, XLS, XLSX | CSV ou XLSX |
| Dados | JSON | JSON |
| Apresentações | PPT, PPTX | PPTX |

Arquivos **DOC**, **XLS** e **PPT** (formatos antigos do Office) não são mesclados diretamente. Abra-os no Word, Excel, PowerPoint ou no LibreOffice e salve como **DOCX** / **XLSX** / **PPTX**.

Formatos mistos (por exemplo MP3 + MP4 + JSON) são rejeitados com a mensagem:

> Os arquivos selecionados possuem formatos incompatíveis. Selecione arquivos compatíveis para realizar a mesclagem.

Imagens podem ser unidas em um PDF. PDFs são unidos página a página.

## Requisitos

- Python 3.10 ou superior
- pip
- FFmpeg e ffprobe, **somente** para áudio e vídeo

JSON, TXT, CSV, PDF, imagens, XLSX, DOCX e PPTX funcionam sem FFmpeg.

## Instalação

No diretório do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Execução

```powershell
python app.py
```

Abra [http://localhost:5111](http://localhost:5111).

A porta fica apenas em `config.py`:

```python
PORT = 5111
```

## FFmpeg (áudio e vídeo)

O FFmpeg é necessário para concatenar MP3, WAV, MP4 e demais mídias. Ele padroniza codec, taxa de amostragem, resolução ou FPS **somente quando a união direta não é possível**.

### Por que é necessário

Bibliotecas Python não concatenam de forma confiável todos os containers de áudio e vídeo. O FFmpeg é a ferramenta consolidada para essa tarefa.

### Windows

Opção 1 — winget:

```powershell
winget install Gyan.FFmpeg
```

Opção 2 — Chocolatey:

```powershell
choco install ffmpeg
```

Opção 3 — instalador manual:

1. Baixe o build em [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/).
2. Extraia para uma pasta permanente, por exemplo `C:\ffmpeg`.
3. Adicione `C:\ffmpeg\bin` ao PATH do Windows:
   - Painel de Controle → Sistema → Configurações avançadas → Variáveis de ambiente
   - Em PATH, inclua a pasta `bin`
4. Feche e reabra o terminal.

### Verificar a instalação

```powershell
ffmpeg -version
ffprobe -version
```

Se os comandos não forem reconhecidos, o PATH ainda não está correto. Reinicie o terminal ou o computador depois de alterar o PATH.

Caminhos manuais podem ser definidos em `config.py`:

```python
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\bin\ffprobe.exe"
```

## Configuração

Tudo que pode variar fica em `config.py`:

- porta e host
- pastas de upload, saída, temporários e logs
- quantidade mínima e máxima de arquivos
- limite de tamanho
- tempo de retenção dos resultados
- caminhos do FFmpeg

## Estrutura

```
mesclador/
├── app.py
├── config.py
├── requirements.txt
├── routes/
├── services/      # um processador por tipo de arquivo
├── utils/
├── templates/
├── static/
├── uploads/
├── outputs/
├── temp/
└── logs/
```

Novos formatos entram como um módulo em `services/` e um item no catálogo de `services/registry.py`, sem reescrever a aplicação.

## WhatsApp

Não há automação contra os mecanismos do WhatsApp. Depois da mesclagem:

- o navegador tenta o compartilhamento nativo (`Web Share API`) quando o sistema permitir;
- caso contrário, abre o WhatsApp Web para você anexar o arquivo baixado manualmente.

## Logs e limpeza

- Logs diários em `logs/`
- Uploads e temporários são removidos após cada operação
- Arquivos de saída antigos são limpos automaticamente após o tempo definido em `OUTPUT_TTL_SECONDS`

## Testes

Com o ambiente virtual ativado:

```powershell
python -m unittest discover -s tests -v
```

Os testes de áudio/vídeo só rodam se o FFmpeg estiver instalado.
