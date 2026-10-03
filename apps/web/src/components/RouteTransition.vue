<script setup lang="ts">
import gsap from 'gsap'
import { KeepAlive } from 'vue'
import { RouterView } from 'vue-router'

const props = defineProps<{
  direction: 'forward' | 'back'
}>()

function onBeforeEnter(el: Element) {
  const offset = props.direction === 'forward' ? 48 : -48
  gsap.set(el, { opacity: 0, x: offset })
}

function onEnter(el: Element, done: () => void) {
  gsap.to(el, {
    opacity: 1,
    x: 0,
    duration: 0.38,
    ease: 'power3.out',
    onComplete: done,
  })
}

function onLeave(el: Element, done: () => void) {
  const offset = props.direction === 'forward' ? -48 : 48
  gsap.to(el, {
    opacity: 0,
    x: offset,
    duration: 0.28,
    ease: 'power3.in',
    onComplete: done,
  })
}
</script>

<template>
  <RouterView v-slot="{ Component, route }">
    <Transition
      :css="false"
      mode="out-in"
      @before-enter="onBeforeEnter"
      @enter="onEnter"
      @leave="onLeave"
    >
      <KeepAlive include="WorkspaceView">
        <component :is="Component" :key="route.path" class="flex min-h-0 flex-1 flex-col" />
      </KeepAlive>
    </Transition>
  </RouterView>
</template>
