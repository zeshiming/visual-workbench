import { describe, expect, it } from 'vitest'

import { flushPromises, mount } from '@vue/test-utils'

import WorkspaceImageViewport from '../components/WorkspaceImageViewport.vue'

async function mockViewportLayout(
  wrapper: ReturnType<typeof mount>,
  options: {
    viewportWidth?: number
    viewportHeight?: number
    imageWidth?: number
    imageHeight?: number
  } = {},
): Promise<HTMLDivElement> {
  const {
    viewportWidth = 800,
    viewportHeight = 600,
    imageWidth = 1200,
    imageHeight = 900,
  } = options

  await flushPromises()

  const viewport = wrapper.find('[data-testid="image-viewport"]').element as HTMLDivElement
  viewport.getBoundingClientRect = () =>
    ({
      width: viewportWidth,
      height: viewportHeight,
      top: 0,
      left: 0,
      right: viewportWidth,
      bottom: viewportHeight,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }) as DOMRect

  const image = wrapper.find('img').element as HTMLImageElement
  Object.defineProperty(image, 'naturalWidth', { value: imageWidth, configurable: true })
  Object.defineProperty(image, 'naturalHeight', { value: imageHeight, configurable: true })

  await wrapper.find('img').trigger('load')
  await flushPromises()

  return viewport
}

function getTransformStyle(wrapper: ReturnType<typeof mount>): string {
  return wrapper.find('[data-testid="image-viewport"] > .absolute').attributes('style') ?? ''
}

function parseTransform(style: string): { scale: number; translateX: number; translateY: number } {
  const scaleMatch = style.match(/scale\(([0-9.]+)\)/)
  const translateMatch = style.match(/translate\(([0-9.]+)px, ([0-9.]+)px\)/)

  return {
    scale: Number(scaleMatch?.[1]),
    translateX: Number(translateMatch?.[1]),
    translateY: Number(translateMatch?.[2]),
  }
}

describe('WorkspaceImageViewport', () => {
  it('fits image to viewport on load', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    await mockViewportLayout(wrapper)

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.scale).toBeCloseTo(0.56, 2)
    expect(transform.translateX).toBeCloseTo(64, 0)
    expect(transform.translateY).toBeCloseTo(48, 0)

    wrapper.unmount()
  })

  it('zooms in when scrolling mouse wheel up', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)

    viewport.dispatchEvent(
      new WheelEvent('wheel', {
        deltaY: -100,
        deltaMode: WheelEvent.DOM_DELTA_LINE,
        clientX: 400,
        clientY: 300,
        bubbles: true,
      }),
    )
    await flushPromises()

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.scale).toBeCloseTo(0.616, 2)

    wrapper.unmount()
  })

  it('pans view when scrolling on trackpad', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)
    const before = parseTransform(getTransformStyle(wrapper))

    viewport.dispatchEvent(
      new WheelEvent('wheel', {
        deltaX: 30,
        deltaY: 20,
        deltaMode: WheelEvent.DOM_DELTA_PIXEL,
        clientX: 400,
        clientY: 300,
        bubbles: true,
      }),
    )
    await flushPromises()

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.scale).toBeCloseTo(before.scale, 5)
    expect(transform.translateX).toBeCloseTo(before.translateX - 30, 0)
    expect(transform.translateY).toBeCloseTo(before.translateY - 20, 0)

    wrapper.unmount()
  })

  it('zooms in when pinching on trackpad', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)

    viewport.dispatchEvent(
      new WheelEvent('wheel', {
        deltaY: -100,
        deltaMode: WheelEvent.DOM_DELTA_PIXEL,
        ctrlKey: true,
        clientX: 400,
        clientY: 300,
        bubbles: true,
      }),
    )
    await flushPromises()

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.scale).toBeCloseTo(0.616, 2)

    wrapper.unmount()
  })

  it('pans view when dragging with primary mouse button', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)

    viewport.dispatchEvent(
      new PointerEvent('pointerdown', {
        button: 0,
        pointerId: 1,
        clientX: 100,
        clientY: 100,
        bubbles: true,
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent('pointermove', {
        pointerId: 1,
        clientX: 150,
        clientY: 120,
        bubbles: true,
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent('pointerup', {
        button: 0,
        pointerId: 1,
        clientX: 150,
        clientY: 120,
        bubbles: true,
      }),
    )
    await flushPromises()

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.translateX).toBeCloseTo(114, 0)
    expect(transform.translateY).toBeCloseTo(68, 0)

    wrapper.unmount()
  })

  it('pans view when dragging with middle mouse button', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)

    viewport.dispatchEvent(
      new PointerEvent('pointerdown', {
        button: 1,
        pointerId: 1,
        clientX: 100,
        clientY: 100,
        bubbles: true,
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent('pointermove', {
        pointerId: 1,
        clientX: 150,
        clientY: 120,
        bubbles: true,
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent('pointerup', {
        button: 1,
        pointerId: 1,
        clientX: 150,
        clientY: 120,
        bubbles: true,
      }),
    )
    await flushPromises()

    const transform = parseTransform(getTransformStyle(wrapper))
    expect(transform.translateX).toBeCloseTo(114, 0)
    expect(transform.translateY).toBeCloseTo(68, 0)

    wrapper.unmount()
  })

  it('renders numbered mark overlays', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
        annotationMode: true,
        marks: [
          {
            id: 'mark-1',
            centerX: 0.5,
            centerY: 0.5,
            radius: 0.1,
            description: '',
          },
        ],
      },
      attachTo: document.body,
    })

    await mockViewportLayout(wrapper)

    expect(wrapper.find('text').text()).toBe('1')

    wrapper.unmount()
  })

  it('resets view to fit when clicking the fit button', async () => {
    const wrapper = mount(WorkspaceImageViewport, {
      props: {
        src: 'data:image/png;base64,abc',
      },
      attachTo: document.body,
    })

    const viewport = await mockViewportLayout(wrapper)
    const fitted = parseTransform(getTransformStyle(wrapper))

    viewport.dispatchEvent(
      new WheelEvent('wheel', {
        deltaY: -100,
        deltaMode: WheelEvent.DOM_DELTA_LINE,
        clientX: 400,
        clientY: 300,
        bubbles: true,
      }),
    )
    await flushPromises()

    const zoomed = parseTransform(getTransformStyle(wrapper))
    expect(zoomed.scale).toBeGreaterThan(fitted.scale)

    await wrapper.get('[aria-label="适应画布"]').trigger('click')
    await flushPromises()

    const reset = parseTransform(getTransformStyle(wrapper))
    expect(reset.scale).toBeCloseTo(fitted.scale, 2)
    expect(reset.translateX).toBeCloseTo(fitted.translateX, 0)
    expect(reset.translateY).toBeCloseTo(fitted.translateY, 0)

    wrapper.unmount()
  })
})
