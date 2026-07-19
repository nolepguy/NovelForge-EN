/*
Environment config file
Development environment
Test environment
Production environment
*/
// Current environment
const env = 'local'

const EnvConfig = {
    local: {
        baseApi: 'http://localhost:54321',
    },
    prod: {
        baseApi: 'http://localhost:54321',

    },
}

export default {
    env,
    // Global mock switch
    ...EnvConfig[env]
}
