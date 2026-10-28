# 0005. Modo seco por padrão e regras em ordem fixa

**Estado:** aceita

## Contexto

Um controlador que aciona hardware não pode começar acionando. E é preciso saber, antes de ligar, o que ele teria feito.

## Decisão

O modo inicial é `dry_run`: o controlador decide e registra `would_pulse`, sem enviar comandos. A política avalia as regras em ordem fixa, com as que impedem primeiro e o modo seco por último, para que registre exatamente o que o modo real faria. O modo `experiment` sorteia blocos de horas de controle, determinista pela semente e pela data.

## Consequências

- Dá para validar a política com dados reais antes de acionar qualquer coisa.
- O modo real é uma escolha explícita (`-Mode live`).
- A ordem das regras vira parte do contrato de comportamento: mudá-la exige atualizar testes e a [arquitetura](../arquitetura.md).
