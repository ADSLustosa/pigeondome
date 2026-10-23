export function ChartLegend() {
  return (
    <ul className="legend" aria-label="Legenda do gráfico">
      <li>
        <span className="legend__swatch legend__swatch--mean" aria-hidden="true" />
        Média de pombos no intervalo
      </li>
      <li>
        <span className="legend__swatch legend__swatch--peak" aria-hidden="true" />
        Pico (maior leitura)
      </li>
      <li>
        <span className="legend__swatch legend__swatch--gap" aria-hidden="true" />
        Sem medição (câmera sem enviar dados)
      </li>
    </ul>
  )
}
