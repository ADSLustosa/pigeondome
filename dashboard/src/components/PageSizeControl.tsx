import { PAGE_SIZES } from '../lib/paging'
import type { PageSize } from '../lib/paging'

interface PageSizeControlProps {
  /** Identifica o grupo: duas trilhas na mesma página não podem compartilhar o mesmo nome. */
  name: string
  value: PageSize
  onChange: (size: PageSize) => void
}

export function PageSizeControl({ name, value, onChange }: PageSizeControlProps) {
  return (
    <fieldset className="field">
      <legend className="field__label">Linhas</legend>
      <div className="segmented">
        {PAGE_SIZES.map((size) => (
          <label key={size} className="segmented__option">
            <input
              type="radio"
              name={`${name}-page-size`}
              value={size}
              checked={value === size}
              onChange={() => onChange(size)}
            />
            <span>{size}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
