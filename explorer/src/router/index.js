import Vue from 'vue'
import Router from 'vue-router'
import Video from '@/views/Video'

Vue.use(Router)

export default new Router({
  routes: [
    {
      path: '/',
      redirect: '/video'
    },
    {
      path: '/video',
      name: 'Video',
      component: Video
    }
  ]
})
