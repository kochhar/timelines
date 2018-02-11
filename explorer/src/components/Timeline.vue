<template>
  <div class="timeline">
    <div id="timeline-target"></div>
  </div>
</template>

<script>

import timeline_json from '../data/example_timeline.json'

export default {
  data() {
    return {
      timeline_json,
      timeline: null
    }
  },
  mounted() {
    this.timeline = new TL.Timeline('timeline-target', this.timeline_json, {timenav_height: 100})
  }
}
</script>

<style lang="scss" scoped>
.timeline {
  width: 80%;
  margin: 20px auto;
  height: 300px;
  border: 1px solid tomtato;
}
</style>
