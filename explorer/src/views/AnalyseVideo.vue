<template>
  <div class="analyse-video">
    <div class="columns">
      <div class="column is-5">
        <timeline-simple :video-id="videoId"></timeline-simple>
      </div>
      <div class="column is-7">
        <div class="youtube-container">
          <youtube :video-id="videoId" :player-height="300" :player-width="500"></youtube>
        </div>
      </div>
    </div>
  </div>
</template>

<script>

import TimelineSimple from '../components/TimelineSimple'

export default {
  components: {
    TimelineSimple
  },
  data() {
    return {
      videoId: 'veMFCFyOwFI'
    }
  }
}
</script>

<style lang="scss" scoped>
.analyse-video {
  font-size: 10px;
}
.youtube-container {
  position:fixed;
}
</style>
