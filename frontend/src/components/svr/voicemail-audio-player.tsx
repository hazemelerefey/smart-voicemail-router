import { useEffect, useRef, useState } from 'react'
import { Pause, Play, Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'

function formatClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '0:00'
  const total = Math.floor(sec)
  const mins = Math.floor(total / 60)
  const rem = total % 60
  return `${mins}:${rem.toString().padStart(2, '0')}`
}

const SPEEDS = [1, 1.25, 1.5] as const

export function VoicemailAudioPlayer({
  src,
  initialDurationSeconds = 0,
  className = '',
}: {
  src: string
  initialDurationSeconds?: number
  className?: string
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(initialDurationSeconds)
  const [speedIdx, setSpeedIdx] = useState(0)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    setPlaying(false)
    setCurrentTime(0)
    setDuration(initialDurationSeconds)
    setLoadError(false)
  }, [src, initialDurationSeconds])

  const effectiveDuration = duration > 0 ? duration : initialDurationSeconds
  const progressPct = effectiveDuration > 0 ? Math.min(100, (currentTime / effectiveDuration) * 100) : 0

  const togglePlay = async () => {
    const el = audioRef.current
    if (!el) return
    if (el.paused) {
      setLoadError(false)
      try {
        await el.play()
        setPlaying(true)
      } catch {
        setPlaying(false)
        setLoadError(true)
      }
    } else {
      el.pause()
      setPlaying(false)
    }
  }

  const toggleMute = () => {
    const el = audioRef.current
    if (!el) return
    el.muted = !el.muted
    setMuted(el.muted)
  }

  const cycleSpeed = () => {
    const next = (speedIdx + 1) % SPEEDS.length
    setSpeedIdx(next)
    if (audioRef.current) {
      audioRef.current.playbackRate = SPEEDS[next]
    }
  }

  const handleSeek = (value: number) => {
    const el = audioRef.current
    setCurrentTime(value)
    if (el && Number.isFinite(value)) {
      el.currentTime = value
    }
  }

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className='flex items-center gap-3 rounded-xl border border-border bg-muted/40 px-3 py-2 shadow-xs dark:bg-muted/25'>
        <audio
          ref={audioRef}
          src={src}
          preload='metadata'
          onLoadedMetadata={(e) => {
            const d = e.currentTarget.duration
            if (Number.isFinite(d) && d > 0) setDuration(d)
            setLoadError(false)
          }}
          onError={() => {
            setPlaying(false)
            setLoadError(true)
          }}
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => {
            setPlaying(false)
            setCurrentTime(0)
          }}
        />

      <Button
        type='button'
        size='icon'
        onClick={() => void togglePlay()}
        aria-label={playing ? 'Pause voicemail audio' : 'Play voicemail audio'}
        className='size-9 shrink-0 rounded-full bg-primary text-primary-foreground shadow-sm hover:bg-primary/90'
      >
        {playing ? (
          <Pause className='size-4 fill-current' />
        ) : (
          <Play className='size-4 translate-x-0.5 fill-current' />
        )}
      </Button>

      <div className='flex min-w-0 flex-1 items-center gap-2.5'>
        <span className='shrink-0 font-mono text-xs font-medium tabular-nums text-foreground'>
          {formatClock(currentTime)}
          <span className='text-muted-foreground'> / {formatClock(effectiveDuration)}</span>
        </span>

        <div className='relative flex flex-1 items-center'>
          <input
            type='range'
            min={0}
            max={effectiveDuration > 0 ? effectiveDuration : 1}
            step={0.1}
            value={Math.min(currentTime, effectiveDuration || 1)}
            onChange={(e) => handleSeek(Number(e.target.value))}
            aria-label='Seek voicemail audio'
            className='h-1.5 w-full cursor-pointer appearance-none rounded-full accent-[#2979FF]'
            style={{
              background: `linear-gradient(to right, #2979FF ${progressPct}%, rgb(148 163 184 / 0.3) ${progressPct}%)`,
            }}
          />
        </div>
      </div>

      <Button
        type='button'
        variant='ghost'
        size='sm'
        onClick={cycleSpeed}
        aria-label={`Playback speed ${SPEEDS[speedIdx]}x`}
        className='h-7 shrink-0 px-2 font-mono text-[11px] font-semibold text-muted-foreground hover:text-foreground'
      >
        {SPEEDS[speedIdx]}x
      </Button>

      <Button
        type='button'
        variant='ghost'
        size='icon'
        onClick={toggleMute}
        aria-label={muted ? 'Unmute audio' : 'Mute audio'}
        className='size-8 shrink-0 text-muted-foreground hover:text-foreground'
      >
        {muted ? <VolumeX className='size-4 text-destructive' /> : <Volume2 className='size-4' />}
      </Button>
      </div>
      {loadError && (
        <span className='px-1 text-xs text-destructive'>
          Audio recording unavailable on server (stream failed to load).
        </span>
      )}
    </div>
  )
}
