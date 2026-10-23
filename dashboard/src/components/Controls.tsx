import type { Device } from '../api/types'
import { WINDOW_PRESETS } from '../lib/windows'
import type { WindowId } from '../lib/windows'

interface ControlsProps {
  devices: Device[]
  deviceId: string | null
  onDeviceChange: (deviceId: string) => void
  windowId: WindowId
  onWindowChange: (windowId: WindowId) => void
}

export function Controls({
  devices,
  deviceId,
  onDeviceChange,
  windowId,
  onWindowChange,
}: ControlsProps) {
  return (
    <div className="controls">
      <label className="field">
        <span className="field__label">Dispositivo</span>
        <select
          value={deviceId ?? ''}
          onChange={(event) => onDeviceChange(event.target.value)}
          disabled={devices.length === 0}
        >
          {devices.map((device) => (
            <option key={device.device_id} value={device.device_id}>
              {device.device_id}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="field">
        <legend className="field__label">Período</legend>
        <div className="segmented">
          {WINDOW_PRESETS.map((preset) => (
            <label key={preset.id} className="segmented__option">
              <input
                type="radio"
                name="window"
                value={preset.id}
                checked={preset.id === windowId}
                onChange={() => onWindowChange(preset.id)}
              />
              <span>{preset.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  )
}
