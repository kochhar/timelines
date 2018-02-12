<template>
  <div class="timeline-simple">
    <table class="table is-bordered">
      <tbody>
        <tr v-for="sent in sentencesWithMatch">
          <td>{{sent.text}}</td>
          <td>
            <table class="table">
              <tbody>
                <tr v-for="event in sent.events">
                  <td>{{event.date}}</td>
                  <td>{{event.match}}</td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>

export default {
  props: {
    videoId: String
  },
  data() {
    return {
      videoData: this.$store.matchData[2]
    }
  },
  computed: {
    sentences() {
      return this.videoData.captions.sents.map((sent, i) => {
        return {
          text: sent,
          captionEnts: this.videoData.captions.ents[i],
          heidelSents: this.videoData.heidel.sents[i],
          events: this.videoData.events[i],
        }
      })
    },
    sentencesWithDate() {
      return this.sentences.filter(s => s.events && s.events.length);
    },
    sentencesWithWiki() {
      return this.sentencesWithDate.filter(s => s.events.filter(e => e.wiki.length).length)
    },
    sentencesWithMatch() {
      return this.sentencesWithWiki.filter(s => s.events.filter(e => e.match).length)
    }
  },
  methods: {
    log(item) {
      console.log(item);
    }
  } 
}
</script>

<style lang="scss" scoped>
</style>
