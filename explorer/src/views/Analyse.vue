<template>
  <div class="analyse">
    <table class="table is-bordered">
      <tbody>
        <tr v-for="sent in dataBySentence">
          <td @click="logSent()">{{sent.text}}</td>
          <!-- captionEnts -->
          <td>
            <table class="table is-bordered">
              <tr v-for="ent in sent.captionEnts">
                <td>{{ent}}</td>
              </tr>
            </table>
          </td>
          <!-- events -->
          <td>
            <table class="table is-bordered">
              <tr v-for="event in sent.events">
                <td>{{event.date}} << {{event.text}}</td>
                <td>
                  <table class="table" v-if="event.wiki.length">
                    <tr v-for="(w,i) in event.wiki">
                      <td>{{w.text}}</td>
                      <td>{{event.scores[i]}}</td>
                    </tr>
                  </table>
                  <div v-else>No Wiki</div>
                </td>
                <td>
                  <table class="table" v-if="event.match">
                    <tr v-for="w in event.match">
                      <td>{{w.text}}</td>
                    </tr>
                  </table>
                  <div v-else>no match</div>
                </td>
                <!-- <td>{{event.ents}}</td> -->
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.item">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.before">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.after">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
                <td>{{event.match}}</td>
              </tr>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>

import pythonData from '../data/match-veMFCFyOwFI-f_any6o3.json'

export default {
  data() {
    return {
      data: pythonData
    }
  },
  computed: {
    dataBySentence() {
      return this.data.captions.sents.map((sent, i) => {
        return {
          text: sent,
          captionEnts: this.data.captions.ents[i],
          heidelSents: this.data.heidel.sents[i],
          events: this.data.events[i],
        }
      })
    }
  },
  methods: {
   
  }
}
</script>

<style lang="scss" scoped>
.analyse {
  font-size: 10px;
}
</style>
