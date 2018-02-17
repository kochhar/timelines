<template>
  <div class="video">
    <div class="title">Timelines Project</div>
    <!-- <timeline></timeline> -->
    <youtube :video-id="videoId" @ready="ready" :player-height="300" :player-width="500"></youtube>
  </div>
</template>

<script>

// import Timeline from '@/components/Timeline'

export default {
  components: {
    // Timeline
  },
  data() {
    return {
      videoId: 'JFpanWNgfQY',
      player: null
    }
  },
  methods: {
    ready(player) {
      this.player = player
    }
  }
}
</script>

<style lang="scss" scoped>
.video {
  text-align: center;
}
</style>
