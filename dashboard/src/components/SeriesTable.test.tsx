import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BucketName, Series, SeriesPoint } from '../api/types'
import { formatDateTime } from '../lib/format'
import { SeriesTable } from './SeriesTable'

const point = (bucketStart: string): SeriesPoint => ({
  bucket_start: bucketStart,
  readings: 30,
  readings_with_pigeons: 30,
  presence_rate: 1,
  mean_pigeons: 4,
  max_pigeons: 9,
})

const makeSeries = (bucket: BucketName, starts: string[]): Series => ({
  device_id: 'cam-sim-01',
  start: '2026-10-24T00:00:00Z',
  end: '2026-10-27T00:00:00Z',
  bucket,
  points: starts.map(point),
})

// dez minutos de diferença nunca atravessam a meia-noite em nenhum fuso horário real,
// e dois dias de diferença nunca caem no mesmo dia: o teste não depende do fuso da máquina
const SAME_DAY = ['2026-10-24T06:00:00Z', '2026-10-24T06:10:00Z', '2026-10-24T06:20:00Z']
const THREE_DAYS = ['2026-10-24T06:00:00Z', '2026-10-24T06:10:00Z', '2026-10-26T06:00:00Z']

describe('SeriesTable', () => {
  it('mostra o dia só na primeira linha e quando ele muda', () => {
    const { container } = render(<SeriesTable series={makeSeries('5m', THREE_DAYS)} />)
    expect(container.querySelectorAll('tbody tr')).toHaveLength(3)
    expect(container.querySelectorAll('.data-table__day')).toHaveLength(2)
  })

  it('mostra o dia uma única vez quando todas as linhas são do mesmo dia', () => {
    const { container } = render(<SeriesTable series={makeSeries('5m', SAME_DAY)} />)
    expect(container.querySelectorAll('.data-table__day')).toHaveLength(1)
  })

  it('toda linha guarda o dia para leitores de tela, mesmo sem mostrá-lo', () => {
    const { container } = render(<SeriesTable series={makeSeries('5m', SAME_DAY)} />)
    const labels = Array.from(container.querySelectorAll('tbody th time')).map(
      (time) => time.textContent,
    )
    expect(labels).toHaveLength(3)
    for (const label of labels) expect(label).toMatch(/^\d{2}\/10 \d{2}:\d{2}:\d{2}$/)
  })

  it('mostra segundos só quando o intervalo é menor que 1 h', () => {
    const minutes = render(<SeriesTable series={makeSeries('1m', SAME_DAY)} />)
    const withSeconds = Array.from(minutes.container.querySelectorAll('.data-table__clock'))
    expect(withSeconds).toHaveLength(3)
    for (const clock of withSeconds) expect(clock.textContent).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    minutes.unmount()

    const hours = render(<SeriesTable series={makeSeries('1h', SAME_DAY)} />)
    const withoutSeconds = Array.from(hours.container.querySelectorAll('.data-table__clock'))
    expect(withoutSeconds).toHaveLength(3)
    for (const clock of withoutSeconds) expect(clock.textContent).toMatch(/^\d{2}:\d{2}$/)
  })

  it('guarda o nome completo da coluna para leitores de tela e esconde a versão curta', () => {
    const { container } = render(<SeriesTable series={makeSeries('5m', SAME_DAY)} />)
    for (const name of ['Início do intervalo', 'Leituras', 'Presença', 'Média', 'Pico']) {
      expect(screen.getByRole('columnheader', { name, hidden: true })).toBeInTheDocument()
    }
    const shorts = Array.from(container.querySelectorAll('.col-short'))
    expect(shorts.map((short) => short.textContent)).toEqual([
      'Início',
      'Leit.',
      'Pres.',
      'Méd.',
      'Pico',
    ])
    for (const short of shorts) expect(short).toHaveAttribute('aria-hidden', 'true')
  })

  it('cada linha traz o instante completo e os valores formatados', () => {
    const { container } = render(<SeriesTable series={makeSeries('5m', SAME_DAY)} />)
    const row = container.querySelector('tbody tr')
    expect(row).not.toBeNull()
    const time = row?.querySelector('time')
    expect(time).toHaveAttribute('datetime', '2026-10-24T06:00:00Z')
    expect(time).toHaveAttribute('title', formatDateTime('2026-10-24T06:00:00Z'))
    const values = Array.from(row?.querySelectorAll('td') ?? []).map((cell) => cell.textContent)
    expect(values).toEqual(['30', '100%', '4,0', '9'])
  })
})
