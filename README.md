# ⬡ NEURODRIVE: Plataforma Experimental de Física e Álgebra Linear

**Neurodrive** é um projeto de integração em IoT e Visão Computacional criado como Solução Digital (A3) para as Unidades Curriculares de Fenômenos Físicos Eletromagnéticos e Modelagem Matemática/Álgebra Linear.

Através de uma maquete física (escala 1:30) operada via smartphone, o sistema processa imagens e sensores em tempo real, extraindo a odometria e projetando os dados num *dashboard* web responsivo.

## ⚙️ Tecnologias e Ementa Aplicada

- **Cálculo Diferencial e Equações Diferenciais:** Simulações e resoluções numéricas (`scipy.integrate.odeint`) de equações de 1ª e 2ª ordem para modelar a Força Contra-Eletromotriz do motor DC e circuitos RLC.
- **Álgebra Linear e Matrizes:** Processamento em tempo real do sinal de vídeo utilizando OpenCV e NumPy, aplicando transformações em matrizes (Optical Flow) e álgebra vetorial para calcular a velocidade de deslocamento.
- **Física Eletromagnética:** Avaliação prática da Lei de Faraday no motor, correntes induzidas e estudo de controle de potência utilizando PWM (Modulação por Largura de Pulso) aplicado em Eletrodinâmica.
- **Números Complexos:** Implementação da Transformada Rápida de Fourier (FFT) em sinais reais para isolar frequências harmônicas, essencial no estudo de fenômenos oscilatórios.

## 🚀 Como Executar o Projeto

**Pré-requisitos:** Python 3.10+

1. Clone este repositório ou faça o download dos arquivos.
2. No terminal (dentro da pasta do projeto), instale todas as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicie o Servidor Central:
   ```bash
   python web_server.py
   ```
4. Acesse o **Dashboard Cyberpunk** através do seu navegador em `http://localhost:5000`.

## 📁 Estrutura do Código-Fonte

- `web_server.py`: Servidor HTTP desenvolvido em Flask. Mantém a conexão EventSource (SSE) com latência nula (bypass stream).
- `neurodrive_pipeline.py`: O "cérebro" matemático. Contém a classe `OdometriaVisual`, que resolve matrizes frame a frame e aplica os cálculos cinemáticos no fluxo de vídeo.
- `web/`: Diretório contendo a interface em HTML5, JavaScript vanilla (`app.js`) e CSS moderno (`style.css`), desenhada com UX responsiva e metodologia científica.
- `analise_frequencia.py` e simuladores: Scripts paralelos de cálculo numérico (SciPy) para a geração de gráficos matemáticos a respeito das frequências de ruído, RLC e circuitos.

---
**Projeto desenvolvido como desempenho de compreensão para a Avaliação A3.**
