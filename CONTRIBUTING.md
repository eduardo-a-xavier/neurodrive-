# 🤝 Guia de Contribuição - NeuroDrive & Carrinho Kizumba 4x4

Agradecemos imensamente seu interesse em contribuir com nosso projeto! Este documento fornece as diretrizes e instruções necessárias para garantir um ambiente colaborativo e padronizado.

---

## 📋 Índice

- [Como Começar](#-como-começar)
- [Reportando Bugs](#-reportando-bugs)
- [Sugerindo Melhorias](#-sugerindo-melhorias)
- [Pull Requests](#-pull-requests)
- [Padrões de Código](#-padrões-de-código)
- [Commits](#-commits)
- [Testes](#-testes)
- [Código de Conduta](#️-código-de-conduta)

---

## 🚀 Como Começar

### 1. Fork o Repositório
Clique no botão "Fork" no topo da página do repositório no GitHub para criar a sua própria cópia.

### 2. Clone Seu Fork
```bash
git clone https://github.com/seu-usuario/neurodrive.git
cd neurodrive
```

### 3. Crie um Ambiente Virtual
Para isolar as dependências (recomendado):
```bash
python -m venv venv
# No Linux/Mac:
source venv/bin/activate
# No Windows:
venv\Scripts\activate
```

### 4. Instale as Dependências
```bash
pip install -r requirements.txt
```

### 5. Crie uma Branch para Sua Feature ou Fix
```bash
git checkout -b feature/minha-feature-incrivel
```

---

## 🐛 Reportando Bugs

Antes de criar um relatório de bug, verifique se o problema já não foi reportado nas [Issues](https://github.com/eduardo-a-xavier/neurodrive/issues).

### Como Enviar Um Bom Relatório de Bug
Forneça as seguintes informações detalhadas:
- **Título descritivo:** Uma descrição clara e sucinta do bug.
- **Passo a passo:** Como reproduzir o problema exato.
- **Comportamento esperado:** O que deveria ter acontecido.
- **Comportamento atual:** O que está efetivamente ocorrendo.
- **Ambiente:** Sistema operacional, versão Python, etc.

---

## 💡 Sugerindo Melhorias

Sugestões de melhorias são tratadas nas [GitHub Issues](https://github.com/eduardo-a-xavier/neurodrive/issues). Ao criar uma sugestão, inclua:
- **Descrição clara:** O que você deseja que seja adicionado ou alterado.
- **Justificativa:** O porquê dessa funcionalidade ser útil ao projeto.
- **Exemplos ou Contexto:** Referências, diagramas, ou links que apoiem sua ideia.

---

## 🔀 Pull Requests

### Processo Básico
1. **Verifique se existe uma issue associada** para evitar trabalho duplicado.
2. **Faça seus commits** de forma atômica e clara.
3. **Faça o Push** para a sua branch no fork (`git push origin feature/minha-feature`).
4. **Abra um Pull Request** no repositório original.
5. **Preencha o template do PR** de forma completa.
6. **Aguarde a revisão** dos mantenedores.

### Checklist do PR
- [ ] Meu código segue os padrões PEP 8 para Python.
- [ ] Eu testei as simulações e/ou pipeline web localmente.
- [ ] Eu atualizei a documentação relevante (se aplicável).
- [ ] Minhas mudanças não quebram funcionalidades existentes.

---

## 📐 Padrões de Código

### Python (PEP 8)
- Utilize 4 espaços para indentação.
- Siga limite de 88 caracteres (recomendado usar `black` como formatter).
- Utilize nomes descritivos.
- Sempre que possível, utilize **Type Hints** e **Docstrings**.

**Exemplo de Docstring:**
```python
def processar_telemetria(dados: dict, threshold: float = 0.5) -> dict:
    """
    Processa os dados de telemetria recebidos do Carrinho Kizumba 4x4.

    Args:
        dados (dict): Dicionário contendo os dados brutos.
        threshold (float): Limite de corte para filtragem de ruído.

    Returns:
        dict: Dados limpos e processados.
    """
    pass
```

---

## 📝 Commits

Utilizamos o formato **Conventional Commits**:
```
<tipo>(<escopo>): <assunto>

<corpo_opcional>
```

### Tipos Permitidos:
- `feat`: Nova funcionalidade.
- `fix`: Correção de um bug.
- `docs`: Atualizações de documentação.
- `style`: Formatação, pontos e vírgulas, sem mudança de lógica de código.
- `refactor`: Refatoração do código em produção.
- `test`: Adição de testes em falta ou refatoração.
- `chore`: Atualização de tarefas de build, gerenciadores de pacotes, etc.

---

## 🧪 Testes

Se estiver adicionando uma funcionalidade de simulação física ou processamento visual, inclua ou rode os testes:
```bash
python -m pytest
```

---

## ⚖️ Código de Conduta

Nós nos dedicamos a fornecer uma experiência livre de assédio para todos, independentemente de gênero, identidade e expressão de gênero, orientação sexual, deficiência, aparência física, tamanho do corpo, idade, raça ou religião.

Não toleramos qualquer tipo de assédio em nossa comunidade. Qualquer membro que violar estas regras poderá ser expulso a critério da equipe de moderação.

**Obrigado mais uma vez por contribuir com o NeuroDrive! 🎉**
