// The Vue build version to load with the `import` command
// (runtime-only or standalone) has been set in webpack.base.conf with an alias.
import Vue from 'vue'
import App from './App'
import router from './router'
import store from './store'
import VueYouTubeEmbed from 'vue-youtube-embed'

Vue.use(VueYouTubeEmbed)

Vue.config.productionTip = false

// Vue.prototype.$TL = TL
Vue.prototype.$store = store

/* eslint-disable no-new */
new Vue({
  el: '#app',
  router,
  components: { App },
  template: '<App/>'
})
