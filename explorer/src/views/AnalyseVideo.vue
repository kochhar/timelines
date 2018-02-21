<template>
  <div class="analyse-video" ref="container">
    <div class="title">Timelines Dev Edition</div>
    <div class="buttons">
      <button class="button is-small"
      v-for="vid in videoIdArr" 
      :class="{'is-info': currVideoId == vid}" 
      @click="currVideoId = vid">{{vid}}</button>
    </div>
    <div v-if="currVideoId">
      <div class="youtube-container">
        <youtube :video-id="currVideoId" :player-height="playerHeight" :player-width="playerWidth" @ready="ready" @playing="playing"></youtube>
      </div>
      <div class="timeline-container" :style="{'padding-top': (playerHeight*1.1)+'px'}">
        <timeline-simple :video-id="currVideoId" :curr-time="currTime" @timestamp-change="timestampChangeHandler"></timeline-simple>
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
      currVideoId: null,
      player: null,
      currTime: null
    }
  },
  computed: {
    playerWidth() {
      return Math.min(700, this.$refs.container.offsetWidth);
    },
    playerHeight() {
      return this.playerWidth * 9/16;
    },
    videoIdArr() {
      return this.$store.wikidatas.map(wd => wd.video_id);
    }
  },
  watch: {
    currVideoId() {
      console.log('changed');
      clearInterval(this.interval);
      setTimeout(this.startInterval, 5000);
    }
  },
  methods: {
    ready(player) {
      this.player = player;
    },
    playing(player) {
      console.log('playing event');
    },
    timestampChangeHandler(ts) {
      return this.player.seekTo(ts);
    },
    startInterval() {
      this.player.playVideo();
      this.interval = setInterval(() => {
        if(!this.currVideoId) clearInterval(this.interval);
        this.currTime = this.player.getCurrentTime();
      }, 2000);
    }
  }
}
</script>

<style lang="scss" scoped>
.analyse-video {
  font-size: 10px;
  margin: 0 auto;
  text-align: center;
}
.youtube-container {
  position:fixed;
  z-index: 100;
  left: 0;
  right: 0;
  margin: auto;
}
</style>
