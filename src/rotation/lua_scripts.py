# ---------------------------------------------------------------------------
# Lua scripts for atomic proxy rotation executed inside Redis.
# Each script is designed to be registered via redis-py's register_script()
# and invoked with the documented KEYS / ARGV parameters.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ROTATE_ROUND_ROBIN
# Rotates proxies in a LIST using LMOVE (right -> left) and returns the first
# healthy, non-blacklisted proxy.
#
# KEYS[1] = pool:{pool_id}:proxies   (LIST)
# ARGV[1] = project_id               (for blacklist check)
# ---------------------------------------------------------------------------
ROTATE_ROUND_ROBIN = """
local pool_key = KEYS[1]
local project_id = ARGV[1]
local pool_size = redis.call('LLEN', pool_key)
if pool_size == 0 then return nil end

for i = 1, pool_size do
    local proxy_id = redis.call('LMOVE', pool_key, pool_key, 'RIGHT', 'LEFT')
    local health = redis.call('GET', 'proxy:' .. proxy_id .. ':health')
    if health ~= 'dead' then
        if project_id and project_id ~= '' then
            local blacklisted = redis.call('SISMEMBER', 'blacklist:' .. project_id, proxy_id)
            if blacklisted == 0 then
                return proxy_id
            end
        else
            return proxy_id
        end
    end
end
return nil
"""

# ---------------------------------------------------------------------------
# ROTATE_RANDOM
# Picks a random starting index and iterates through the LIST looking for a
# healthy, non-blacklisted proxy.
#
# KEYS[1] = pool:{pool_id}:proxies   (LIST)
# ARGV[1] = project_id               (for blacklist check)
# ---------------------------------------------------------------------------
ROTATE_RANDOM = """
local pool_key = KEYS[1]
local project_id = ARGV[1]
local pool_size = redis.call('LLEN', pool_key)
if pool_size == 0 then return nil end

local start = math.random(0, pool_size - 1)
for i = 0, pool_size - 1 do
    local idx = (start + i) % pool_size
    local proxy_id = redis.call('LINDEX', pool_key, idx)
    local health = redis.call('GET', 'proxy:' .. proxy_id .. ':health')
    if health ~= 'dead' then
        if project_id and project_id ~= '' then
            local blacklisted = redis.call('SISMEMBER', 'blacklist:' .. project_id, proxy_id)
            if blacklisted == 0 then
                return proxy_id
            end
        else
            return proxy_id
        end
    end
end
return nil
"""

# ---------------------------------------------------------------------------
# ROTATE_WEIGHTED_RANDOM
# Uses a ZSET where each member is a proxy_id and each score is its weight.
# Picks a random cumulative-weight threshold and walks the ZSET to find the
# matching proxy, skipping dead or blacklisted entries.
#
# KEYS[1] = pool:{pool_id}:weighted  (ZSET: proxy_id -> weight)
# ARGV[1] = project_id               (for blacklist check)
# ---------------------------------------------------------------------------
ROTATE_WEIGHTED_RANDOM = """
local weighted_key = KEYS[1]
local project_id = ARGV[1]

local members = redis.call('ZRANGEBYSCORE', weighted_key, '-inf', '+inf', 'WITHSCORES')
local count = #members / 2
if count == 0 then return nil end

-- Build a table of {proxy_id, weight} pairs, filtering out dead/blacklisted
local candidates = {}
local total_weight = 0
for i = 1, #members, 2 do
    local proxy_id = members[i]
    local weight = tonumber(members[i + 1])
    local health = redis.call('GET', 'proxy:' .. proxy_id .. ':health')
    if health ~= 'dead' then
        local skip = false
        if project_id and project_id ~= '' then
            local blacklisted = redis.call('SISMEMBER', 'blacklist:' .. project_id, proxy_id)
            if blacklisted == 1 then
                skip = true
            end
        end
        if not skip then
            total_weight = total_weight + weight
            candidates[#candidates + 1] = {proxy_id, weight}
        end
    end
end

if total_weight == 0 or #candidates == 0 then return nil end

-- Pick a random threshold and find the matching candidate
local threshold = math.random() * total_weight
local cumulative = 0
for _, entry in ipairs(candidates) do
    cumulative = cumulative + entry[2]
    if cumulative >= threshold then
        return entry[1]
    end
end

-- Fallback to last candidate (floating-point edge case)
return candidates[#candidates][1]
"""

# ---------------------------------------------------------------------------
# ROTATE_LEAST_CONNECTIONS
# Uses a ZSET where each member is a proxy_id and each score is the current
# connection count.  Returns the proxy with the lowest score that is healthy
# and not blacklisted, then atomically increments its score by 1.
#
# KEYS[1] = pool:{pool_id}:connections  (ZSET: proxy_id -> connection_count)
# ARGV[1] = project_id                  (for blacklist check)
# ---------------------------------------------------------------------------
ROTATE_LEAST_CONNECTIONS = """
local connections_key = KEYS[1]
local project_id = ARGV[1]

-- Get all members sorted by score ascending (least connections first)
local members = redis.call('ZRANGEBYSCORE', connections_key, '-inf', '+inf', 'WITHSCORES')
local count = #members / 2
if count == 0 then return nil end

for i = 1, #members, 2 do
    local proxy_id = members[i]
    local health = redis.call('GET', 'proxy:' .. proxy_id .. ':health')
    if health ~= 'dead' then
        local skip = false
        if project_id and project_id ~= '' then
            local blacklisted = redis.call('SISMEMBER', 'blacklist:' .. project_id, proxy_id)
            if blacklisted == 1 then
                skip = true
            end
        end
        if not skip then
            -- Atomically increment connection count
            redis.call('ZINCRBY', connections_key, 1, proxy_id)
            return proxy_id
        end
    end
end

return nil
"""

# ---------------------------------------------------------------------------
# RATE_LIMIT_CHECK
# Sliding-window rate limiter using a simple INCR + TTL pattern.
# Returns 1 if the request is allowed, 0 if rate-limited.
#
# KEYS[1] = ratelimit:{project_id}:{window}
# ARGV[1] = limit          (max requests per window)
# ARGV[2] = window_seconds  (TTL for the counter key)
# ---------------------------------------------------------------------------
RATE_LIMIT_CHECK = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window_seconds)
end

if current > limit then
    return 0
end
return 1
"""
