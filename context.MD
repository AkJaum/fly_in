# Fly-in: Contexto de Desenvolvimento

> Este documento e a referencia principal para o desenvolvimento do projeto
> **Fly-in**. Toda decisao de arquitetura, implementacao, teste e documentacao
> deve respeitar os requisitos descritos aqui.

## 1. Objetivo do Projeto

O Fly-in simula o transporte de drones entre um hub inicial e um hub final por
meio de um grafo nao direcionado e ponderado. A simulacao acontece em turnos e
deve encontrar rotas eficientes, respeitando capacidades de zonas e conexoes,
custos de movimento e conflitos entre drones.

Os principais objetivos sao:

- entregar todos os drones ao hub final;
- produzir uma simulacao valida turno a turno;
- minimizar o numero total de turnos;
- evitar conflitos, bloqueios e deadlocks;
- oferecer uma representacao visual util da simulacao.

## 2. Restricoes Tecnicas Criticas

### 2.1 Proibicoes

- **Bibliotecas de grafos:** e proibido usar `networkx`, `graphlib` ou qualquer
  biblioteca que implemente ou auxilie diretamente a logica de grafos.
- A estrutura do grafo e os algoritmos de busca devem ser implementados no
  proprio projeto.

### 2.2 Requisitos de codigo

- O projeto deve ser totalmente orientado a objetos.
- Todas as classes, funcoes, metodos, parametros e retornos devem possuir type
  hints.
- O projeto deve passar no `mypy` sem erros.
- O codigo deve respeitar o `flake8`.
- Todas as classes, funcoes e metodos devem possuir docstrings conforme a
  PEP 257.
- A versao minima da linguagem e Python 3.10.

### 2.3 Makefile

O `Makefile` deve conter, no minimo, as regras:

- `install`: instala as dependencias;
- `run`: executa o programa;
- `debug`: executa em modo de depuracao;
- `clean`: remove arquivos temporarios e caches;
- `lint`: executa `flake8` e `mypy` com as flags definidas pelo projeto.

## 3. Modelo de Dominio

O sistema deve ser dividido nas entidades abaixo. Quando exigido pela
arquitetura do projeto, atributos de classe podem manter os registros globais
das instancias criadas.

### 3.1 `Zone`

Representa um hub do mapa.

**Atributos principais:**

- `name`: nome unico, sem hifens ou espacos;
- `pos`: coordenadas inteiras `(x, y)`;
- `kind`: `normal`, `restricted`, `priority` ou `blocked`;
- `max_drones`: capacidade maxima, com valor padrao `1`;
- `weight`: peso usado pelo algoritmo de pathfinding.

**Regras de capacidade:**

- `start_hub` e `end_hub` possuem capacidade infinita;
- todas as demais zonas respeitam `max_drones`;
- `max_drones` deve ser um inteiro positivo.

### 3.2 `Connection`

Representa uma ligacao bidirecional entre duas zonas.

**Atributos principais:**

- `previous_zone`;
- `next_zone`;
- `max_link_capacity`, com valor padrao `1`.

**Regras:**

- toda conexao e bidirecional;
- `max_link_capacity` deve ser um inteiro positivo;
- uma conexao ocupa capacidade enquanto um drone estiver em transito;
- conexoes `a-b` e `b-a` representam a mesma conexao e nao podem coexistir.

### 3.3 `Drone`

Representa um drone participante da simulacao.

**Atributos principais:**

- `id`: identificador no formato `D1`, `D2`, etc.;
- `path`: caminho calculado;
- `route`: estado ou progresso atual na rota.

**Metodos esperados:**

- `act()`;
- `move()`;
- `path_finding()`.

### 3.4 `MapParser`

Responsavel por ler o arquivo de entrada, criar as entidades e rejeitar dados
invalidos. Consulte a secao [6. Regras do Parser](#6-regras-do-parser).

### 3.5 `Graph`

Responsavel por:

- armazenar e gerenciar a topologia;
- associar conexoes as zonas correspondentes;
- oferecer operacoes de consulta necessarias ao pathfinding;
- manter a implementacao do grafo independente de bibliotecas externas.

### 3.6 `Simulation`

Responsavel por:

- executar o loop de turnos;
- planejar e aplicar movimentos simultaneos;
- respeitar capacidades de zonas e conexoes;
- coletar as linhas de output;
- identificar drones entregues;
- encerrar quando todos os drones chegarem ao hub final.

## 4. Tipos de Zona e Custos

O custo de um movimento e determinado pelo tipo da **zona de destino**.

| Tipo | Duracao real | Preferencia no pathfinding | Pode entrar? |
| --- | ---: | ---: | --- |
| `normal` | 1 turno | peso `1` | Sim |
| `restricted` | 2 turnos | peso `2` | Sim |
| `priority` | 1 turno | peso preferencial, por exemplo `0.5` | Sim |
| `blocked` | Infinita | peso infinito | Nao |

> **Distincao obrigatoria:** uma zona `priority` sempre leva **1 turno** para ser
> alcancada. O valor `0.5` pode ser usado somente como peso de escolha no
> pathfinding para favorecer essa zona; ele nao representa meio turno na
> simulacao.

## 5. Mecanica da Simulacao

### 5.1 Turnos e simultaneidade

- A simulacao ocorre em turnos discretos.
- Varios drones podem se mover no mesmo turno quando todas as capacidades forem
  respeitadas.
- Movimentos de um mesmo turno devem ser avaliados como simultaneos.
- Um drone que sai de uma zona libera espaco para outro drone entrar nessa mesma
  zona durante o mesmo turno.
- Drones sem movimento em um turno nao aparecem no output daquele turno.
- Ao chegar ao `end_hub`, o drone e considerado entregue e deixa de ser
  rastreado pela simulacao.

### 5.2 Movimentos para zonas restritas

- Entrar em uma zona `restricted` exige 2 turnos.
- No primeiro turno, o drone entra na conexao e ocupa sua capacidade.
- No segundo turno, o drone deve obrigatoriamente chegar a zona de destino.
- O drone nao pode aguardar na conexao por espaco livre.
- Portanto, antes de iniciar o movimento, a simulacao deve garantir que a
  chegada obrigatoria sera valida no turno seguinte.

### 5.3 Conflitos

Uma simulacao valida deve:

- nunca exceder `max_drones` de uma zona;
- nunca exceder `max_link_capacity` de uma conexao;
- impedir a entrada em zonas `blocked`;
- evitar conflitos entre movimentos simultaneos;
- evitar deadlocks;
- distribuir drones entre rotas quando isso reduzir o tempo total.

## 6. Regras do Parser

### 6.1 Estrutura obrigatoria

- A primeira linha deve ser `nb_drones: <positive_integer>`.
- O numero de drones deve ser um inteiro positivo e nao possui limite fixo.
- Deve existir exatamente um `start_hub` e exatamente um `end_hub`.
- Toda zona deve possuir nome unico e coordenadas inteiras validas.
- Conexoes so podem referenciar zonas definidas anteriormente.

### 6.2 Nomes e conexoes

- Nomes de zonas podem usar quaisquer caracteres validos, exceto hifens e
  espacos.
- Uma conexao usa o formato:

  ```text
  connection: <zone1>-<zone2> [metadata]
  ```

- Conexoes duplicadas devem causar erro.
- Como as conexoes sao bidirecionais, `a-b` e `b-a` sao duplicatas.

### 6.3 Metadados

- Blocos de metadados usam colchetes: `[...]`.
- Os campos podem aparecer em qualquer ordem.
- Todo bloco deve ser sintaticamente valido.
- Exemplos:

  ```text
  [zone=priority color=blue]
  [max_link_capacity=2]
  ```

- Tipos de zona aceitos: `normal`, `blocked`, `restricted` e `priority`.
- Qualquer tipo diferente deve causar erro.
- `max_drones` e `max_link_capacity` devem ser inteiros positivos.

### 6.4 Erros

Qualquer erro de parsing deve:

- interromper o programa;
- apresentar uma mensagem clara;
- informar a linha;
- explicar a causa.

Devem existir mapas de teste proprios para casos-limite e entradas invalidas,
alem dos mapas fornecidos pelo subject.

## 7. Pathfinding e Otimizacao

### 7.1 Algoritmo base

Dijkstra e o algoritmo recomendado para calcular caminhos de menor custo. Sua
implementacao deve ser propria e considerar:

- o tipo da zona de destino;
- a inacessibilidade de zonas `blocked`;
- a preferencia por zonas `priority`;
- os custos de zonas `restricted`;
- capacidades e congestionamentos relevantes para a distribuicao de drones.

### 7.2 Estrategia de distribuicao

Encontrar apenas o menor caminho individual pode nao minimizar o tempo total da
simulacao. A estrategia tambem deve considerar:

- uso de multiplos caminhos;
- capacidade das zonas;
- capacidade das conexoes;
- drones ja alocados a cada rota;
- prevencao de deadlocks;
- estimativa do turno de chegada de cada drone.

## 8. Formato de Saida

Cada turno deve gerar exatamente uma linha. Os movimentos sao separados por um
espaco e seguem um dos formatos:

```text
D<ID>-<zone>
D<ID>-<connection>
```

O segundo formato identifica um drone ainda em transito para uma zona
`restricted`.

Exemplo:

```text
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

Regras adicionais:

- drones parados sao omitidos;
- drones entregues nao aparecem em turnos posteriores;
- a simulacao termina quando todos os drones chegam ao `end_hub`.

## 9. Visualizacao

O projeto deve fornecer feedback visual. As opcoes incluem:

- cores no terminal;
- interface grafica com Tkinter;
- interface grafica com Pygame.

A visualizacao deve facilitar a compreensao de:

- posicoes das zonas;
- conexoes do mapa;
- posicao e movimento dos drones;
- zonas bloqueadas, restritas e prioritarias;
- progresso dos turnos e drones entregues.

## 10. Validade e Metricas

O criterio principal de pontuacao e o numero total de turnos necessarios para
entregar todos os drones.

Uma solucao valida deve:

- cumprir todas as regras de movimento e ocupacao;
- aplicar corretamente os custos dos tipos de zona;
- respeitar capacidades de zonas e conexoes;
- evitar todos os conflitos.

Metricas secundarias opcionais:

- numero de drones movidos por turno;
- media de turnos por drone;
- custo total dos caminhos;
- qualidade e utilidade da representacao visual;
- qualidade do codigo.

Em caso de empate no numero de turnos, essas metricas podem ser usadas para
comparar as solucoes.

## 11. Benchmarks de Performance

### 11.1 Metas gerais

| Categoria | Meta |
| --- | ---: |
| Mapas faceis | Menos de 10 turnos |
| Mapas medios | Entre 10 e 30 turnos |
| Mapas dificeis | Menos de 60 turnos |
| Challenger | Bater o recorde de 45 turnos |

### 11.2 Mapas de referencia

| Dificuldade | Mapa | Drones | Meta |
| --- | --- | ---: | ---: |
| Facil | Linear path | 2 | <= 6 turnos |
| Facil | Simple fork | 4 | <= 8 turnos |
| Facil | Basic capacity | 4 | <= 6 turnos |
| Medio | Dead end trap | 5 | <= 12 turnos |
| Medio | Circular loop | 6 | <= 15 turnos |
| Medio | Priority puzzle | 5 | <= 12 turnos |
| Dificil | Maze nightmare | 8 | <= 30 turnos |
| Dificil | Capacity hell | 12 | <= 35 turnos |
| Dificil | Ultimate challenge | 15 | <= 45 turnos |
| Challenger | The Impossible Dream | 25 | < 45 turnos |

O Challenger e opcional e nao afeta a nota da parte obrigatoria.

## 12. Requisitos do README

O arquivo `README.md` deve existir na raiz do repositorio e ser escrito em
ingles.

### 12.1 Primeira linha obrigatoria

A primeira linha deve estar em italico e seguir exatamente este modelo:

```markdown
*This project has been created as part of the 42 curriculum by <login1>[, <login2>[, <login3>[...]]].*
```

### 12.2 Secoes obrigatorias

O README deve conter, no minimo:

- **Description:** objetivo e visao geral do projeto;
- **Instructions:** instalacao, configuracao e execucao;
- **Resources:** referencias classicas e descricao de como a IA foi utilizada,
  incluindo tarefas e partes do projeto;
- descricao detalhada das escolhas de algoritmos;
- estrategia de implementacao;
- documentacao da representacao visual e de como ela melhora a experiencia do
  usuario.

Secoes adicionais podem incluir exemplos de uso, funcionalidades, arquitetura,
testes e decisoes tecnicas.

## 13. Bonus

O bonus sera avaliado somente se todos os requisitos obrigatorios estiverem
corretos.

Possibilidades de bonus:

- igualar ou superar todas as metas de turnos dos mapas fornecidos;
- resolver o mapa `The Impossible Dream`;
- concluir o Challenger em menos de 45 turnos.

## 14. Checklist de Desenvolvimento

- [ ] Projeto 100% orientado a objetos.
- [ ] Nenhuma biblioteca de grafos utilizada.
- [ ] Type hints completos e `mypy` sem erros.
- [ ] Codigo aprovado pelo `flake8`.
- [ ] Docstrings PEP 257 em todas as classes, funcoes e metodos.
- [ ] `Makefile` com `install`, `run`, `debug`, `clean` e `lint`.
- [ ] Parser valida toda a sintaxe e informa linha e causa dos erros.
- [ ] Exatamente um hub inicial e um hub final.
- [ ] Capacidades de zonas e conexoes respeitadas.
- [ ] Movimentos restritos ocupam a conexao e terminam obrigatoriamente.
- [ ] Movimentos simultaneos liberam e ocupam espacos corretamente.
- [ ] Zonas prioritarias sao preferidas sem alterar a duracao real de 1 turno.
- [ ] Zonas bloqueadas nunca sao acessadas.
- [ ] Simulacao evita conflitos e deadlocks.
- [ ] Output segue exatamente o formato exigido.
- [ ] Feedback visual implementado.
- [ ] README em ingles com todas as secoes obrigatorias.
- [ ] Mapas validos, invalidos e casos-limite testados.
- [ ] Benchmarks medidos e documentados.
