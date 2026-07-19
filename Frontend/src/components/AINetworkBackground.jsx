import { useEffect, useRef } from 'react'

export default function AINetworkBackground() {
  const canvasRef = useRef(null)
  const mouseRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0, actualX: undefined, actualY: undefined })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId
    let width = 0
    let height = 0
    let nodes = []
    let particles = []

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const getDensitySettings = (w) => {
      if (w < 650) {
        return { nodeCount: 30, maxDist: 90, particleCount: 20 }
      } else if (w < 900) {
        return { nodeCount: 65, maxDist: 120, particleCount: 35 }
      } else {
        return { nodeCount: 110, maxDist: 150, particleCount: 50 }
      }
    }

    const brandColors = [
      'rgba(196, 181, 253, 0.45)', // #c4b5fd (soft light purple)
      'rgba(129, 140, 248, 0.45)', // #818cf8 (soft indigo/purple)
      'rgba(81, 210, 189, 0.45)'    // #51d2bd (cyan/teal/turquoise)
    ]

    const init = () => {
      width = canvas.width = canvas.offsetWidth
      height = canvas.height = canvas.offsetHeight

      const settings = getDensitySettings(width)
      nodes = []
      particles = []

      for (let i = 0; i < settings.nodeCount; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * (prefersReducedMotion ? 0.05 : 0.25),
          vy: (Math.random() - 0.5) * (prefersReducedMotion ? 0.05 : 0.25),
          radius: Math.random() * 2 + 1.5,
          color: brandColors[Math.floor(Math.random() * brandColors.length)],
          baseAlpha: Math.random() * 0.3 + 0.2,
          pulseSpeed: Math.random() * 0.02 + 0.01,
          pulsePhase: Math.random() * Math.PI * 2
        })
      }

      for (let i = 0; i < settings.particleCount; i++) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * (prefersReducedMotion ? 0.02 : 0.12),
          vy: -Math.random() * (prefersReducedMotion ? 0.05 : 0.25) - 0.05,
          radius: Math.random() * 1 + 0.5,
          alpha: Math.random() * 0.2 + 0.1
        })
      }
    }

    const resize = () => {
      init()
    }

    init()
    window.addEventListener('resize', resize)

    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      mouseRef.current.targetX = (x - width / 2) * 0.04
      mouseRef.current.targetY = (y - height / 2) * 0.04
      mouseRef.current.actualX = x
      mouseRef.current.actualY = y
    }

    const handleMouseLeave = () => {
      mouseRef.current.targetX = 0
      mouseRef.current.targetY = 0
      mouseRef.current.actualX = undefined
      mouseRef.current.actualY = undefined
    }

    const parent = canvas.parentElement
    if (parent) {
      parent.addEventListener('mousemove', handleMouseMove)
      parent.addEventListener('mouseleave', handleMouseLeave)
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)

      const mouse = mouseRef.current
      mouse.x += (mouse.targetX - mouse.x) * 0.08
      mouse.y += (mouse.targetY - mouse.y) * 0.08

      const settings = getDensitySettings(width)

      const bgGlow = ctx.createRadialGradient(
        width / 2 + mouse.x * 2,
        height / 2 + mouse.y * 2,
        10,
        width / 2 + mouse.x * 2,
        height / 2 + mouse.y * 2,
        width * 0.6
      )
      bgGlow.addColorStop(0, 'rgba(39, 32, 64, 0.15)')
      bgGlow.addColorStop(1, 'transparent')
      ctx.fillStyle = bgGlow
      ctx.fillRect(0, 0, width, height)

      ctx.fillStyle = 'rgba(238, 240, 247, 0.15)'
      for (const p of particles) {
        if (!prefersReducedMotion) {
          p.x += p.vx
          p.y += p.vy
          if (p.x < 0) p.x = width
          if (p.x > width) p.x = 0
          if (p.y < 0) p.y = height
        }
        ctx.beginPath()
        ctx.arc(p.x + mouse.x * 0.5, p.y + mouse.y * 0.5, p.radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(238, 240, 247, ${p.alpha})`
        ctx.fill()
      }

      for (const node of nodes) {
        if (!prefersReducedMotion) {
          node.x += node.vx
          node.y += node.y < 0 || node.y > height ? -node.vy : node.vy
          node.x += node.x < 0 || node.x > width ? -node.vx : node.vx
          if (node.x < 0) node.x = 0
          if (node.x > width) node.x = width
          if (node.y < 0) node.y = 0
          if (node.y > height) node.y = height
        }

        node.pulsePhase += node.pulseSpeed
        const pulse = Math.sin(node.pulsePhase) * 0.12

        let mouseInfluence = 0
        if (mouse.actualX !== undefined && mouse.actualY !== undefined) {
          const dx = node.x - mouse.actualX
          const dy = node.y - mouse.actualY
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 200) {
            mouseInfluence = (1 - dist / 200) * 0.35
          }
        }

        const currentAlpha = Math.min(node.baseAlpha + pulse + mouseInfluence, 0.85)

        ctx.beginPath()
        ctx.arc(node.x + mouse.x, node.y + mouse.y, node.radius + pulse * 2, 0, Math.PI * 2)
        ctx.fillStyle = node.color.replace('0.45', currentAlpha.toFixed(2))
        ctx.shadowBlur = 10
        ctx.shadowColor = node.color
        ctx.fill()
        ctx.shadowBlur = 0
      }

      ctx.lineWidth = 0.65
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const n1 = nodes[i]
          const n2 = nodes[j]
          const dx = n1.x - n2.x
          const dy = n1.y - n2.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < settings.maxDist) {
            const alpha = (1 - dist / settings.maxDist) * 0.12
            ctx.beginPath()
            ctx.moveTo(n1.x + mouse.x, n1.y + mouse.y)
            ctx.lineTo(n2.x + mouse.x, n2.y + mouse.y)
            ctx.strokeStyle = `rgba(139, 149, 170, ${alpha.toFixed(3)})`
            ctx.stroke()
          }
        }
      }

      animationFrameId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resize)
      if (parent) {
        parent.removeEventListener('mousemove', handleMouseMove)
        parent.removeEventListener('mouseleave', handleMouseLeave)
      }
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="hero-bg-canvas"
      style={{
        display: 'block',
        width: '100%',
        height: '100%'
      }}
    />
  )
}
