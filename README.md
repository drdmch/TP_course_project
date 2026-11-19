# SIPL Language Toolkit

![CI](https://github.com/drdmch/TP_course_project/actions/workflows/ci.yml/badge.svg)

Курсовий проєкт з «Теорії програмування»: інструменти для мови SIPL.

## Виконані завдання

| ID | Завдання | Бали |
|---|---|---|
| CORE-01 | Граматика Lark за БНФ курсу, 12 коректних і 12 некоректних прикладів | 0.5 |
| CORE-02 | Парсер, AST з позиціями в тексті, повідомлення про помилки | 1.5 |
| CORE-03 | Інтерпретатор з лімітом кроків | 2.0 |
| CORE-04 | Trace виконання | 1.0 |
| CORE-05 | CLI з JSON-режимом | 1.0 |
| VIS-01 | Дерево синтаксичного виводу: text, JSON, DOT, SVG | 1.5 |
| VIS-02 | AST і HTML-порівняння дерева виводу з AST | 1.0 |
| SEM-01 | Побудова семантичного терму (правила NS_*) | 2.0 |
| SEM-02 | Обчислення терму на стані (правила AF_*) | 2.0 |
| REL-01 | GitHub Actions: лінтер, тести, збирання | 0.5 |
| REL-02 | Реліз за тегом, CHANGELOG.txt | 0.5 |
| REL-03 | Публікація на PyPI | 0.5 |
| | **Разом** | **14.0** |

## Деталі виконання

**Граматика і парсер.** Граматика в `sipl.lark` повторює БНФ із практикуму (с. 8–9).
Неоднозначність БНФ знято явними пріоритетами. Lark (LALR) будує дерево розбору,
а клас `ToAst` перетворює його на власні вузли (`Assign`, `While`, `BinOp`, ...).
Кожен вузол має `span`: рядок, колонку і позицію в тексті. Синтаксичні помилки
виводяться у форматі `файл:рядок:колонка` з переліком очікуваних токенів.
Некоректні приклади містять у першому рядку `// error-line: N`, і тест перевіряє,
що помилку знайдено саме в цьому рядку.

**Інтерпретатор.** Стан — словник `змінна -> число`. Читання змінної без значення
є помилкою, а не 0, бо стан, як і в курсі, — часткова функція. `div` і `mod`
округлюють униз. У `∨` завжди обчислюються обидві частини, як у S2(or, f1, f2).
Кроком вважається присвоювання, `skip`, вибір гілки `if` або перевірка умови `while`.
Ліміт кроків (за замовчуванням 100000) зупиняє нескінченні цикли.

**Trace.** Під час виконання записуються події `program_started`, `before_statement`,
`variable_changed`, `condition_evaluated`, `after_statement`, `program_finished`.
Кожна подія містить номер, текст оператора, позицію і стан. У JSON-режимі trace
віддається повністю, у текстовому показуються лише основні рядки.

**Дерево виводу і AST.** Дерево виводу будується з дерева розбору Lark з усіма
токенами. Вузли названо як у практикумі (P, S, a, b, x, n) з номерами правил
(P1, S1–S6, A1–A6, B1–B5). Листки зліва направо дають текст програми, і це
перевіряє тест. SVG малюється власним кодом без Graphviz: листки стоять у ряд,
батько — над серединою своїх дітей. `sipl compare` створює HTML-сторінку з обома
деревами: клік по вузлу підсвічує фрагмент коду і вузли з тим самим фрагментом
в іншому дереві.

**Семантичні терми.** `TermBuilder` рекурсивно обходить AST і застосовує правила
`NS_Prog`, `NS_Stm_As`, `NS_Stm_Seq`, `NS_Stm_If`, `NS_Stm_Wh`, `NS_Stm_BE`,
`NS_Stm_skip`, `NS_A_*`, `NS_B_*`. Кожне застосоване правило записується. Для прикладу
з практикуму виходить той самий терм, що на с. 16:

```
AS^R(1) · WH(S2(gr, Y⇒, 0), AS^R(S2(mult, R⇒, X⇒)) · AS^Y(S2(sub, Y⇒, 1)))
```


## Встановлення

```
pip install sipl-language-toolkit
```

Для розробки:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Команди

```
sipl check examples/valid/power.sipl              # синтаксис і вхідні змінні
sipl run   examples/valid/power.sipl -s X=3 -s Y=4
sipl trace examples/valid/power.sipl -s X=2 -s Y=2
sipl parse examples/valid/power.sipl              # AST
sipl tree  examples/valid/power.sipl              # дерево виводу (--format text|json|dot|svg)
sipl ast   examples/valid/power.sipl --format svg -o ast.svg
sipl compare examples/valid/power.sipl -o compare.html
sipl term  examples/valid/power.sipl --steps      # семантичний терм
sipl eval  examples/valid/power.sipl -s X=5 -s Y=2
```

`--json` дає вивід у JSON для команд parse, check, run, trace, term, eval.

Коди завершення: 0 — успіх, 1 — синтаксична помилка, 2 — неправильні аргументи,
3 — помилка виконання або невизначений результат, 4 — перевищено ліміт кроків.

## Тести

```
pytest
ruff check src tests
```

## Структура

```
src/sipl/
  sipl.lark         граматика
  parser.py         текст -> AST
  ast.py            вузли AST
  interpreter.py    виконання і trace
  semantics.py      семантичні терми
  visualization.py  дерево виводу, AST, SVG, HTML
  cli.py            команди sipl
examples/           приклади програм
tests/              тести, golden/ — еталонні терми
```

## Мова

```
P ::= begin S end
S ::= x := a | S1 ; S2 | if b then S1 else S2 | while b do S | begin S end | skip
a ::= n | x | a1 + a2 | a1 - a2 | a1 * a2 | a1 div a2 | a1 mod a2 | (a)
b ::= a1 = a2 | a1 > a2 | b1 ∨ b2 | ¬ b | (b)
```

`;` має найнижчий пріоритет, `*`, `div`, `mod` — вищий за `+`, `-`, `¬` — вищий за `∨`.
Замість `∨` і `¬` можна писати `or` і `not`. Коментарі: `// ...`.
