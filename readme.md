# VM Translator (VM → Hack Assembly)

Traductor del lenguaje de máquina virtual (VM) de Nand2Tetris a ensamblador Hack, escrito en Python.
Cubre los proyectos 7 y 8: comandos aritméticos y de memoria, control de flujo (`label`, `goto`,
`if-goto`) y funciones (`function`, `call`, `return`), con código de arranque (*bootstrap*).

**Evaluación 3 – Organización de Computadores.** El programa VM de ejemplo calcula la serie

```
  n
  Σ  (i + 2)²        con n constante (en Sys.vm, n = 3)
 i=0
```

Para n = 3: (0+2)² + (1+2)² + (2+2)² + (3+2)² = 4 + 9 + 16 + 25 = **54**.

---

## 1. Estructura del proyecto

```
VM-Translator/
├── Main.py          # Punto de entrada: recorre los .vm y coordina Parser y CodeWriter
├── Parser.py        # Lee un .vm, limpia comentarios y clasifica cada comando
├── CodeWriter.py    # Convierte cada comando VM en instrucciones Hack
├── Main.vm          # Main.computeSum, Main.addTwo, Main.square
├── Sys.vm           # Sys.init
└── VM-Translator.asm   # Salida (se llama como la carpeta)
```

## 2. Cómo usarlo

**Traducir** (desde la carpeta que contiene los scripts):

```bash
python Main.py <carpeta_con_archivos_vm>     # traduce todos los .vm de la carpeta
python Main.py archivo.vm                     # traduce un solo archivo
```

- Con una carpeta, el `.asm` se crea dentro de ella y se llama como la carpeta.
- El código de arranque (*bootstrap*) solo se escribe si la carpeta contiene `Sys.vm`.
  Los tests del proyecto 7 y los de BasicLoop/SimpleFunction/FibonacciSeries no lo necesitan.

**Probar en el CPU Emulator de Nand2Tetris:**

1. Cargar el `.asm` con *Load Program* (el emulador lo ensambla automáticamente).
2. Poner la animación en *No animation* y ejecutar unos segundos. `Sys.init` termina en un
   bucle infinito (`label WHILE` / `goto WHILE`), así que hay que detenerlo manualmente.
3. Comprobar en la RAM: **`RAM[261]` debe valer 54** (el resultado queda donde estaba el
   argumento de `Main.computeSum`).

Para los tests oficiales: traducir la carpeta de cada test, dejar el `.asm` junto a su `.tst`
y `.cmp`, cargar el `.tst` en el CPU Emulator y ejecutar. Debe aparecer
*"Comparison ended successfully"*.

---

## 3. El programa VM

### `Sys.vm`

```
function Sys.init 0
push constant 3            // n = 3
call Main.computeSum 1     // computeSum(3)
label WHILE
goto WHILE                 // fin del programa (bucle infinito)
```

### `Main.vm` (resumen)

| Función | Qué hace |
|---|---|
| `Main.computeSum` (2 locales) | `local 0` = i, `local 1` = suma. Mientras `i <= n`: llama a `addTwo(i)`, pasa ese resultado a `square`, lo suma a `local 1` e incrementa `i`. Devuelve la suma. |
| `Main.addTwo` (0 locales) | Devuelve `argument 0 + 2`. No es recursiva. |
| `Main.square` (2 locales) | Eleva al cuadrado con un bucle de sumas (Hack no tiene multiplicador): suma `x` consigo mismo `x` veces. |

Idea clave de `computeSum`: el resultado de `call Main.addTwo 1` queda **en la pila**, y esa misma
posición sirve directamente como argumento de `call Main.square 1`, sin variables intermedias.

---

## 4. Cómo funciona el traductor

```
archivo.vm ──► Parser ──► (tipo, arg1, arg2) ──► CodeWriter ──► archivo.asm
                 ▲                                     ▲
                 └──────────────── Main ───────────────┘
```

- **Parser**: ignora líneas vacías y comentarios (`//`), separa el comando en palabras y devuelve
  su tipo (`C_ARITHMETIC`, `C_PUSH`, `C_POP`, `C_LABEL`, `C_GOTO`, `C_IF`, `C_FUNCTION`,
  `C_CALL`, `C_RETURN`), `arg1()` y `arg2()`. Si encuentra un comando desconocido, falla con un
  error que indica la línea.
- **CodeWriter**: tiene un método por tipo de comando. Mantiene el nombre del archivo actual (para
  las variables `static`), la función actual (para los *labels*) y un contador (para etiquetas únicas).
- **Main**: ordena los `.vm`, escribe el *bootstrap* si hay `Sys.vm`, y recorre cada archivo
  llamando al método correspondiente del CodeWriter.

### Mapa de memoria Hack que usa el traductor

| Dirección | Uso |
|---|---|
| `RAM[0]` `SP` | Puntero de pila (apunta a la **siguiente** posición libre) |
| `RAM[1]` `LCL` | Base del segmento `local` de la función actual |
| `RAM[2]` `ARG` | Base del segmento `argument` |
| `RAM[3]` `THIS` / `RAM[4]` `THAT` | Bases de `this` / `that` (también `pointer 0` / `pointer 1`) |
| `RAM[5]`–`RAM[12]` | Segmento `temp` |
| `RAM[13]`–`RAM[15]` | Registros temporales del traductor (`R13`, `R14`) |
| `RAM[16]`–`RAM[255]` | Variables `static` (símbolos `Archivo.i`) |
| `RAM[256]`–… | La pila |

### Traducción de comandos

| Comando VM | Idea de la traducción |
|---|---|
| `push constant k` | `D=k`; `RAM[SP]=D`; `SP++` |
| `push local/argument/this/that i` | `D = RAM[base + i]`; apilar `D` |
| `pop local/argument/this/that i` | Calcular `base+i` y guardarlo en `R13`; `SP--`; `RAM[R13] = RAM[SP]` |
| `push/pop temp i` | Dirección fija `5 + i` |
| `push/pop pointer 0/1` | `THIS` / `THAT` |
| `push/pop static i` | Símbolo `NombreArchivo.i` (el ensamblador lo ubica desde `RAM[16]`) |
| `add`, `sub`, `and`, `or` | Sacar `y`, operar sobre `x` en el tope, `SP++` |
| `neg`, `not` | Se opera directamente sobre el tope de la pila |
| `eq`, `gt`, `lt` | Comparación con etiquetas únicas; resultado `-1` (verdadero) o `0` (falso) |
| `label L` | `(funcion$L)` |
| `goto L` | `@funcion$L` + `0;JMP` |
| `if-goto L` | Sacar el tope; si es distinto de 0, saltar a `funcion$L` |
| `function f k` | `(f)` y apilar `k` ceros (inicializa las variables locales) |
| `call f n` | Ver sección 5 |
| `return` | Ver sección 5 |

**Detalles importantes (errores comunes que ya están corregidos):**

- **Orden de operandos en Hack:** el ensamblador oficial solo acepta `D+M`, `D&M` y `D|M`
  (con `D` primero). Por eso `add` genera `M=D+M`, no `M=M+D`.
- **Comparaciones sin desbordamiento:** `x - y` puede desbordar 16 bits si `x` e `y` tienen signos
  distintos (por ejemplo `32767 - (-1)`). `gt` y `lt` comparan primero los signos.
- **Labels dentro de funciones:** se nombran `funcion$label`, así dos funciones pueden usar el mismo
  nombre de label sin que choquen.
- **Direcciones de retorno únicas:** `funcion$ret.N` con un contador que nunca se repite.

---

## 5. `call` y `return` paso a paso (el corazón de la presentación)

### 5.1 `call f n` — guardar el contexto y saltar

Con `n` argumentos ya apilados, el traductor hace:

1. Apila la **dirección de retorno** (`f$ret.N`).
2. Apila `LCL`, `ARG`, `THIS`, `THAT` del que llama (el *frame* guardado, 5 palabras en total).
3. `ARG = SP - n - 5` → `ARG` apunta al primer argumento.
4. `LCL = SP` → las variables locales de la función empiezan justo después del frame.
5. `goto f`.
6. Declara la etiqueta `(f$ret.N)`: el punto al que volverá la ejecución.

```
        Pila al entrar a Main.addTwo (n = 1, i = 0)

  269   0        ← ARG     argumento: i
  270   181                dirección de retorno
  271   267                LCL guardado del que llama
  272   261                ARG guardado del que llama
  273   0                  THIS guardado
  274   0                  THAT guardado
  275            ← LCL, SP  (aquí empiezan las locales de addTwo; tiene 0)
```

### 5.2 `function f k` — reservar locales

Define la etiqueta `(f)` y apila `k` ceros. Así `local 0 … local k-1` empiezan en 0.

### 5.3 `return` — deshacer todo

1. `FRAME = LCL` (se guarda en `R13`).
2. `RET = *(FRAME - 5)` (se guarda en `R14` **antes** de sobrescribir nada; si la función no tiene
   argumentos, el valor de retorno pisaría esa posición).
3. `*ARG = pop()` → el valor de retorno queda donde estaba el primer argumento.
4. `SP = ARG + 1` → la pila queda justo después del valor de retorno.
5. Restaurar `THAT`, `THIS`, `ARG`, `LCL` desde `FRAME-1`, `FRAME-2`, `FRAME-3`, `FRAME-4`.
6. `goto RET`.

**Resultado:** para quien llamó, es como si los `n` argumentos se hubieran reemplazado por un único
valor de retorno.

### 5.4 Bootstrap

```
SP = 256
call Sys.init 0
```

El bootstrap se escribe al principio del `.asm` (ROM[0]) y arranca todo el programa.

---

## 6. Traza real de la pila (n = 3)

Valores medidos ejecutando el `.asm` generado, para la **primera iteración** (i = 0).
La pila empieza en `RAM[256]`.

| Momento | SP | LCL | ARG | Contenido relevante de la pila |
|---|---|---|---|---|
| Entrada a `Main.computeSum` | 267 | 267 | 261 | `261`: n = 3 · `262`: dir. de retorno · `263`: LCL guardado (261) · `264`: ARG guardado (256) |
| Entrada a `Main.addTwo` (i = 0) | 275 | 275 | 269 | `267, 268`: locales de computeSum (0, 0) · `269`: argumento 0 · `270`–`274`: frame |
| Tras `return` de `addTwo` | 270 | 267 | 261 | `269`: **2** (el valor de retorno reemplaza al argumento) |
| Entrada a `Main.square` | 275 | 275 | 269 | `269`: argumento 2 · `270`–`274`: nuevo frame · `275`, `276`: locales de square |
| Tras `return` de `square` | 270 | 267 | 261 | `269`: **4** (2² = 4) |
| 2.ª iteración: tras `addTwo(1)` | 270 | 267 | 261 | `269`: **3** |
| 2.ª iteración: tras `square(3)` | 270 | 267 | 261 | `269`: **9** (y `local 1` = 4 + 9 = 13) |

Acumulado final: 4 → 13 → 29 → **54**.

Observar que **`LCL` y `ARG` vuelven a los valores de `computeSum` (267 y 261) después de cada
`return`**. Eso es lo que demuestra que el frame se guarda y restaura correctamente.

---

## 7. Qué debe llevar la presentación (entregable 2)

El enunciado pide una presentación que **explique de manera simple y visual cómo cambia el estado
de la pila durante el anidamiento de `call` y `return`**. Propuesta de diapositivas:

1. **Portada.** Título, integrantes del grupo, curso, fecha.
2. **Objetivo.** Calcular Σ(i+2)² para i=0..n con un programa VM de varios archivos. Mostrar la
   fórmula y el resultado esperado para n = 3 (54).
3. **Arquitectura del programa.** Un diagrama de las funciones:
   `Sys.init → Main.computeSum → (Main.addTwo, Main.square)`. Indicar qué archivo contiene cada una.
4. **Código VM de cada función.** Mostrar `Sys.vm` y `Main.vm`, con comentarios breves a un lado.
5. **Mapa de memoria.** La tabla de la sección 4 (SP, LCL, ARG, THIS, THAT, temp, static, pila desde 256).
6. **Cómo se traduce (el traductor).** El esquema `Parser → CodeWriter → .asm` y dos o tres ejemplos de
   traducción (por ejemplo `push constant 3`, `add` y `if-goto`).
7. **Bootstrap.** `SP = 256` y `call Sys.init 0`.
8. **Anatomía de `call`.** El dibujo del frame de la sección 5.1: dirección de retorno, LCL, ARG,
   THIS, THAT, y dónde quedan `ARG` y `LCL`. **Usar colores** para distinguir argumentos, frame guardado
   y locales.
9. **Anatomía de `return`.** Los 6 pasos de la sección 5.3, resaltando que el valor de retorno
   reemplaza al primer argumento y que `SP = ARG + 1`.
10. **Animación del anidamiento (la diapositiva principal).** Una secuencia de 5–6 imágenes de la pila
    para la iteración i = 0, usando la tabla de la sección 6:
    - antes de `call addTwo` → dentro de `addTwo` → tras su `return` →
    - dentro de `square` → tras su `return` → suma acumulada en `local 1`.
    Dibujar la pila verticalmente, con flechas para `SP`, `LCL` y `ARG` que se muevan en cada paso.
11. **Resultado.** Captura del CPU Emulator con `RAM[261] = 54`.
12. **Pruebas y problemas encontrados.** Los errores corregidos (sección 4, "Detalles importantes").
13. **Conclusiones.** Qué se aprendió sobre cómo un lenguaje de alto nivel se apoya en una pila.

**Consejos para que sea "simple y visual":** poco texto por diapositiva; la pila siempre dibujada en
la misma posición y con la misma escala; un color por tipo de dato; los números reales de la tabla
de la sección 6 y no valores inventados.

---

## 8. Preparación para la sustentación (entregable 3)

Un integrante elegido al azar debe explicar el trabajo. **Todos** deberían saber responder:

- **¿Para qué sirve el bootstrap?** Inicializa `SP = 256` y llama a `Sys.init`, que es el punto de
  entrada del programa.
- **¿Por qué `call` guarda 5 valores?** Dirección de retorno, `LCL`, `ARG`, `THIS`, `THAT`: son todo lo
  que hay que restaurar para que el que llamó continúe como si nada hubiera pasado.
- **¿Por qué `ARG = SP - n - 5`?** Después de apilar el frame (5 palabras), el primer argumento
  quedó 5 + n posiciones por debajo de `SP`.
- **¿Por qué se guarda `RET` en `R14` antes de escribir el valor de retorno?** Si la función no tiene
  argumentos, `*ARG` coincide con la posición de la dirección de retorno y la pisaría.
- **¿Por qué `SP = ARG + 1`?** Deja la pila con el valor de retorno en el tope, como si los argumentos
  hubieran sido reemplazados por él.
- **¿Qué hace `function f k`?** Pone la etiqueta `f` y apila `k` ceros para las variables locales.
- **¿Cómo funciona `if-goto`?** Saca el tope de la pila; si es distinto de cero salta, si no continúa.
- **¿Por qué `true` es `-1`?** En Hack, `-1` son todos los bits en 1, lo que hace que `and`, `or` y `not`
  funcionen como operadores lógicos.
- **¿Cómo multiplica `Main.square` sin multiplicador?** Con un bucle que suma `x` consigo mismo
  `x` veces.
- **¿Por qué los labels llevan `funcion$`?** Para que dos funciones puedan usar el mismo nombre de
  label sin conflicto.
- **¿Por qué `M=D+M` y no `M=M+D`?** La ALU de Hack y el ensamblador oficial solo reconocen la
  forma con `D` primero.

---

## 9. Limitaciones conocidas

- `Main.square` solo funciona con argumentos **no negativos**: con un valor negativo el contador `j`
  nunca iguala a `x` y el bucle no termina. Como `n` es una constante positiva, no afecta este ejercicio.
- El traductor asume que el `.vm` es válido; los errores de sintaxis del VM no se verifican en detalle.
- Si hay varios archivos con funciones del mismo nombre, no se detecta el duplicado.