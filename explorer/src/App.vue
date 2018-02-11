<template>
  <div id="app">
    <router-view/>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style lang="scss">

$primary: #2070bb;
@import "../node_modules/bulma/bulma.sass";

#app {
  /* font-family: 'Avenir', Helvetica, Arial, sans-serif; */
  // font-family: 'Roboto', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0px auto;
  padding: 40px;
  max-width: 1000px;
}
</style>
